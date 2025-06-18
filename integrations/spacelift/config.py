# from pydantic import BaseSettings, Field
# import os
# from dotenv import load_dotenv
# load_dotenv()
# print(os.getcwd())  # Check current working directory
# print(os.listdir('.'))  # Check if .env is present

# print("SPACELIFT_API_KEY_ID:", os.getenv("SPACELIFT_API_KEY_ID"))
# print("SPACELIFT_API_KEY_SECRET:", os.getenv("SPACELIFT_API_KEY_SECRET"))
# class SpaceliftConfig(BaseSettings):
#     spacelift_account: str = Field(..., alias="spacelift_account")
#     api_key_id: str = Field(..., alias="SPACELIFT_API_KEY_ID")
#     api_key_secret: str = Field(..., alias="SPACELIFT_API_KEY_SECRET")
#     port_client_id: str = Field(..., alias="PORT_CLIENT_ID")
#     port_client_secret: str = Field(..., alias="PORT_CLIENT_SECRET")

#     class Config:
#         env_file = ".env"
#         env_file_encoding = "utf-8"
#         # env_prefix is not needed here, since we use explicit aliases




from pydantic import BaseSettings

class SpaceliftConfig(BaseSettings):
    spacelift_account: str
    SPACELIFT_API_KEY_ID: str
    SPACELIFT_API_KEY_SECRET: str
    PORT_CLIENT_ID: str
    PORT_CLIENT_SECRET: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
