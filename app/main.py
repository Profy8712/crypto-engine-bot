from .engine import Engine
from dotenv import load_dotenv

def main():
    load_dotenv()
    Engine().run("app/config/config.example.json")

if __name__ == "__main__":
    main()
