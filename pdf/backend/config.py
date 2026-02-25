from pydantic_settings import BaseSettings
from typing import Optional
import os
from cryptography.fernet import Fernet
import json

class Settings(BaseSettings):
    app_name: str = "PDF OCR Web Application"
    max_file_size: int = 500 * 1024 * 1024
    upload_dir: str = "uploads"
    output_dir: str = "outputs"
    ocrmypdf_languages: list = ["chi_sim", "eng"]
    
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    
    key_file: str = "secret.key"
    
    class Config:
        env_file = ".env"

settings = Settings()

def get_fernet_key() -> bytes:
    key_path = settings.key_file
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
        return key

fernet = Fernet(get_fernet_key())

def encrypt_api_key(api_key: str) -> str:
    return fernet.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    return fernet.decrypt(encrypted_key.encode()).decode()

def save_llm_config(api_key: str, base_url: str, model: str):
    config = {
        "api_key": encrypt_api_key(api_key) if api_key else "",
        "base_url": base_url,
        "model": model
    }
    with open("llm_config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def load_llm_config() -> dict:
    if os.path.exists("llm_config.json"):
        with open("llm_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
            if config.get("api_key"):
                try:
                    config["api_key"] = decrypt_api_key(config["api_key"])
                except:
                    config["api_key"] = ""
            return config
    return {
        "api_key": "",
        "base_url": settings.llm_base_url,
        "model": settings.llm_model
    }
