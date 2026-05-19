1. Create virtual environment

         py -m venv venv
Activate it:

- Windows:

        venv\Scripts\actívate

2. Install dependencies

         pip install -r requirements.txt

If requirements.txt is not available:

         pip install pandas langchain chromadb ollama langchain-ollama

3. Install and run the LLM

Install Ollama from its official website. (https://ollama.com/download)

Then run:

         ollama run phi3

First time will download the model (~2GB)
After it loads, exit with:

         /exit
Then execute the following commands:
         ollama pull nomic-embed-text
         ollama pull phi3:mini

4. Run the system

         python rag_artworks_system.py
