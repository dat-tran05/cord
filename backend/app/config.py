from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI
    openai_api_key: str
    openai_realtime_model: str = "gpt-realtime-mini"
    openai_supervisor_model: str = "gpt-5.2"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    frontend_url: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
