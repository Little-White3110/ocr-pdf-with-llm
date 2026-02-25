import asyncio
import os
import subprocess
import shutil
import traceback
import concurrent.futures
import re
from typing import Optional, Callable, List
from pypdf import PdfReader, PdfWriter
from config import settings

executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

class OCRProcessor:
    def __init__(self):
        self.upload_dir = settings.upload_dir
        self.output_dir = settings.output_dir
        self._ensure_directories()
        self.available_languages = self._get_available_languages()
        self.current_process = None
        print(f"Available Tesseract languages: {self.available_languages}")
    
    def _ensure_directories(self):
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _get_available_languages(self) -> List[str]:
        try:
            result = subprocess.run(
                ["tesseract", "--list-langs"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                langs = result.stdout.strip().split('\n')[1:]
                return [lang.strip() for lang in langs if lang.strip() and lang.strip() != 'osd']
            return ['eng']
        except Exception:
            return ['eng']
    
    def _get_ocr_languages(self) -> tuple:
        primary_langs = []
        
        if 'chi_sim' in self.available_languages:
            primary_langs.append('chi_sim')
        
        if 'chi_sim_vert' in self.available_languages:
            primary_langs.append('chi_sim_vert')
        
        if 'eng' in self.available_languages:
            primary_langs.append('eng')
        
        if not primary_langs:
            primary_langs = self.available_languages[:1] if self.available_languages else ['eng']
        
        equ_available = 'equ' in self.available_languages
        
        return primary_langs, equ_available
    
    def _run_ocr_sync(self, cmd: List[str]) -> tuple:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.current_process = process
        
        try:
            stdout, stderr = process.communicate()
            return process.returncode, stdout, stderr
        except Exception as e:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except:
                    process.kill()
            raise e
        finally:
            self.current_process = None
    
    def cancel_current_process(self):
        if self.current_process and self.current_process.poll() is None:
            print("Cancelling OCR process...")
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except:
                self.current_process.kill()
            self.current_process = None
    
    def _clean_text(self, text: str) -> str:
        def remove_chinese_spaces(match):
            return match.group(1) + match.group(2)
        
        for _ in range(10):
            new_text = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', remove_chinese_spaces, text)
            if new_text == text:
                break
            text = new_text
        
        text = re.sub(r'([\u4e00-\u9fff])\s+([，。！？、；：""''（）【】《》])', r'\1\2', text)
        text = re.sub(r'([，。！？、；：""''（）【】《》])\s+([\u4e00-\u9fff])', r'\1\2', text)
        
        text = re.sub(r'\.{3,}', '……', text)
        text = re.sub(r'…+', '……', text)
        text = re.sub(r'-{3,}', '——', text)
        text = re.sub(r'—{2,}', '——', text)
        text = re.sub(r'_{3,}', '____', text)
        
        text = re.sub(r'([^\s])\.{2,}(\d+)', r'\1……\2', text)
        text = re.sub(r'([^\s])-{2,}(\d+)', r'\1——\2', text)
        
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'[ \t]+\n', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)
        return '\n'.join(cleaned_lines)
    
    async def process_pdf(
        self,
        input_path: str,
        output_path: str,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        is_cancelled: Optional[Callable[[], bool]] = None
    ) -> bool:
        try:
            if is_cancelled and is_cancelled():
                return False
            
            if progress_callback:
                progress_callback(10, "正在准备 OCR 处理...")
            
            primary_langs, equ_available = self._get_ocr_languages()
            lang_str = "+".join(primary_langs)
            
            if is_cancelled and is_cancelled():
                return False
            
            if progress_callback:
                lang_desc = "中英文" if 'chi_sim' in primary_langs else "英文"
                progress_callback(20, f"正在执行 OCR 识别 ({lang_desc})...")
            
            sidecar_path = output_path.replace('.pdf', '.txt')
            
            cmd = [
                "ocrmypdf",
                "--force-ocr",
                "-l", lang_str,
                "--oversample", "400",
                "--tesseract-oem", "1",
                "--tesseract-pagesegmode", "6",
                "--optimize", "0",
                "--sidecar", sidecar_path,
                input_path,
                output_path
            ]
            
            print(f"OCR command: {' '.join(cmd)}")
            
            loop = asyncio.get_event_loop()
            
            def run_with_cancel_check():
                future = executor.submit(self._run_ocr_sync, cmd)
                
                import time
                while not future.done():
                    if is_cancelled and is_cancelled():
                        self.cancel_current_process()
                        future.cancel()
                        return -1, "", "Cancelled"
                    time.sleep(0.5)
                
                try:
                    return future.result()
                except:
                    return -1, "", "Cancelled"
            
            returncode, stdout_str, stderr_str = await loop.run_in_executor(
                None, run_with_cancel_check
            )
            
            if returncode == -1:
                print("OCR was cancelled")
                return False
            
            print(f"OCR return code: {returncode}")
            print(f"OCR stderr: {stderr_str[:500] if stderr_str else 'empty'}")
            
            if returncode not in [0, 1, 2, 3, 4, 5, 6, 9]:
                if "Failed loading language" in stderr_str or "language is not supported" in stderr_str:
                    raise Exception(f"Tesseract 语言包错误: {stderr_str[:200]}")
                else:
                    raise Exception(f"OCR 处理失败: {stderr_str[:300] if stderr_str else '未知错误'}")
            
            if returncode in [3, 9]:
                print(f"OCR returned code {returncode} (some pages had warnings), continuing...")
            
            if os.path.exists(sidecar_path):
                with open(sidecar_path, 'r', encoding='utf-8', errors='ignore') as f:
                    raw_text = f.read()
                cleaned_text = self._clean_text(raw_text)
                with open(sidecar_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_text)
                print(f"Sidecar text cleaned: {sidecar_path}")
            
            if progress_callback:
                progress_callback(90, "OCR 处理完成")
            
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                print(f"Output file exists: {output_path}, size: {os.path.getsize(output_path)}")
                return True
            else:
                print(f"Output file not found or empty, copying input to output")
                shutil.copy(input_path, output_path)
                return True
                
        except FileNotFoundError as e:
            print(f"FileNotFoundError: {e}")
            raise Exception(f"OCR 工具未找到: {str(e)}，请确保已安装 OCRmyPDF 和 Tesseract")
        except asyncio.TimeoutError:
            print(f"TimeoutError")
            raise Exception("OCR 处理超时")
        except Exception as e:
            print(f"Exception in process_pdf: {type(e).__name__}: {e}")
            print(traceback.format_exc())
            if "OCR" in str(e) or "Ghostscript" in str(e) or "Tesseract" in str(e):
                raise
            raise Exception(f"OCR 处理出错: {str(e)}")
    
    def get_pdf_page_count(self, pdf_path: str) -> int:
        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except:
            return 0
    
    def extract_text_from_pages(
        self,
        pdf_path: str,
        start_page: int,
        end_page: int
    ) -> str:
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for i in range(start_page - 1, min(end_page, len(reader.pages))):
                page = reader.pages[i]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
            return self._clean_text(text)
        except Exception as e:
            raise Exception(f"提取文本失败: {str(e)}")
    
    def extract_all_text(self, pdf_path: str) -> str:
        try:
            sidecar_path = pdf_path.replace('.pdf', '.txt')
            if os.path.exists(sidecar_path):
                with open(sidecar_path, 'r', encoding='utf-8') as f:
                    return f.read()
            
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
            return self._clean_text(text)
        except Exception as e:
            raise Exception(f"提取文本失败: {str(e)}")
    
    def get_sidecar_path(self, pdf_path: str) -> str:
        return pdf_path.replace('.pdf', '.txt')

ocr_processor = OCRProcessor()
