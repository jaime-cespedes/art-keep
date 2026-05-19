import os
import shutil
import json
import tkinter as tk
from tkinter.scrolledtext import ScrolledText

from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings, OllamaLLM
from langchain_community.vectorstores import Chroma

# ---------------------------------------------------
# PASO 1: Cargar JSON
# ---------------------------------------------------

print("📊 Loading database...")

with open("museo.json", "r", encoding="utf-8") as f:
    museo_data = json.load(f)

salas_dict = {sala["id"]: sala for sala in museo_data.get("salas", [])}

documents = []

for cuadro in museo_data.get("cuadros", []):

    sala = salas_dict.get(cuadro["sala"], {})
    nombre_sala = sala.get("nombre", f"Room {cuadro['sala']}")
    epoca = sala.get("epoca", "Unknown")

    text = (
        f"The artwork '{cuadro['nombre']}' is described as: "
        f"'{cuadro['descripcion']}'. "
        f"It belongs to the '{epoca}' period and is located in "
        f"{nombre_sala}. "
        f"[System coordinates X: {cuadro['x']}, "
        f"Y: {cuadro['y']}, ID: {cuadro['id']}]"
    )

    metadata = {
        "id": cuadro['id'],
        "title": cuadro['nombre'],
        "author": "anonymous",
        "period": epoca
    }

    documents.append(
        Document(
            page_content=text,
            metadata=metadata
        )
    )

print(f"✅ {len(documents)} documents created.")

# ---------------------------------------------------
# PASO 2: Embeddings
# ---------------------------------------------------

print("🧠 Generating embeddings...")

embeddings = OllamaEmbeddings(model="nomic-embed-text")

# ---------------------------------------------------
# PASO 3: Base vectorial
# ---------------------------------------------------

persist_directory = "./artworks_vector_db"

if os.path.exists(persist_directory):
    shutil.rmtree(persist_directory)

vectorstore = Chroma.from_documents(
    documents,
    embedding=embeddings,
    persist_directory=persist_directory
)

vectorstore.persist()

print("✅ Vectorial database created successfully.")

retriever = vectorstore.as_retriever(
    search_kwargs={"k": 3}
)

# ---------------------------------------------------
# PASO 4: Cargar LLM
# ---------------------------------------------------

print("🤖 Loading model phi3...")

llm = OllamaLLM(model="phi3:mini")

print("\n🎉 RAG System Ready.\n")

# ---------------------------------------------------
# DETECCIÓN DE NAVEGACIÓN
# ---------------------------------------------------

def detect_navigation_intent(query):

    query = query.lower()

    navigation_keywords = [
        "take me",
        "go to",
        "guide me",
        "navigate",
        "show me",
        "bring me",
        "tour",
        "renaissance",
        "modern",
        "romanticism",
        "postimpressionism",
        "renacimiento",
        "moderno",
        "romanticismo",
        "postimpresionismo"
    ]

    return any(
        keyword in query
        for keyword in navigation_keywords
    )

# ---------------------------------------------------
# GENERAR MISIÓN
# ---------------------------------------------------
VISITOR_ID = 1

MISSION_FILE = f"C:/Users/domit/Desktop/UPM/8vo semestre/ATA/proyecto/ArtKeep/ATA_MUSEO_TIAGO_DDS_FINAL/ATA_MUSEO_TIAGO_DDS_FINAL/controllers/artkeep_shared/mission_command_{VISITOR_ID}.json"



def generate_mission_file(doc, query):

    query_lower = query.lower()

    # =====================================================
    # TOUR RENACIMIENTO
    # =====================================================

    if (
        "renaissance" in query_lower or
        "renacimiento" in query_lower
    ):

        command = {
            "modo": 2,
            "sala_id": 1
        }

    # =====================================================
    # TOUR MODERNO
    # =====================================================

    elif (
        "modern" in query_lower or
        "moderno" in query_lower
    ):

        command = {
            "modo": 2,
            "sala_id": 2
        }

    # =====================================================
    # TOUR ROMANTICISMO
    # =====================================================

    elif (
        "romanticism" in query_lower or
        "romanticismo" in query_lower or
        "postimpressionism" in query_lower or
        "postimpresionismo" in query_lower
    ):

        command = {
            "modo": 2,
            "sala_id": 3
        }

    # =====================================================
    # CUADRO INDIVIDUAL
    # =====================================================

    else:

        artwork_id = doc.metadata.get("id")

        command = {
            "modo": 1,
            "cuadro_id": artwork_id
        }

    # =====================================================
    # EVITAR SOBREESCRITURA
    # =====================================================

    if os.path.exists(MISSION_FILE):

        chat.insert(
            tk.END,
            "\n⏳ Webots still processing previous mission...\n"
        )

        return

    # =====================================================
    # GUARDAR JSON
    # =====================================================

    with open(MISSION_FILE, "w", encoding="utf-8") as f:
        json.dump(command, f, indent=4)

    print("📡 Mission sent to Webots:")
    print(command)

# ---------------------------------------------------
# PROCESAR CONSULTA
# ---------------------------------------------------

def procesar_consulta():

    query = entrada.get()

    if not query.strip():
        return

    entrada.delete(0, tk.END)

    chat.insert(
        tk.END,
        f"\n👤 Visitor:\n{query}\n"
    )

    query_lower = query.lower()

    matched_docs = []

    # ---------------------------------------------------
    # FILTRADO EXACTO
    # ---------------------------------------------------

    for doc in documents:

        title = str(
            doc.metadata.get('title', '')
        ).lower()

        author = str(
            doc.metadata.get('author', '')
        ).lower()

        period = str(
            doc.metadata.get('period', '')
        ).lower()

        clean_title = title.split('(')[0].strip()

        last_name = (
            author.split()[-1]
            if author else ""
        )

        if (
            clean_title in query_lower or
            period in query_lower or
            (
                author != "anonymous" and
                (
                    author in query_lower or
                    last_name in query_lower
                )
            )
        ):
            matched_docs.append(doc)

    # ---------------------------------------------------
    # VECTOR SEARCH
    # ---------------------------------------------------

    retrieved_docs = (
        matched_docs
        if matched_docs
        else retriever.invoke(query)
    )

    # ---------------------------------------------------
    # SIN RESULTADOS
    # ---------------------------------------------------

    if not retrieved_docs:

        chat.insert(
            tk.END,
            "\n🤖 TIAGo:\n"
            "I do not have information in the database.\n"
        )

        return

    # ---------------------------------------------------
    # CONTEXTO
    # ---------------------------------------------------

    context = "\n".join(
        [doc.page_content for doc in retrieved_docs]
    )

    # ---------------------------------------------------
    # PROMPT
    # ---------------------------------------------------

    prompt = f"""
    You are a friendly museum guide assistant.

    STRICT RULES:
    - Use ONLY the provided context.
    - Never use external knowledge.
    - Never mention coordinates or internal IDs.

    CONTEXT:
    {context}

    QUESTION:
    {query}

    ANSWER:
    """

    response = llm.invoke(prompt)

    # ---------------------------------------------------
    # MOSTRAR RESPUESTA
    # ---------------------------------------------------

    chat.insert(
        tk.END,
        f"\n🤖 TIAGo:\n{response}\n"
    )

    # ---------------------------------------------------
    # ENVIAR MISIÓN
    # ---------------------------------------------------

    if detect_navigation_intent(query):

        selected_doc = retrieved_docs[0]

        generate_mission_file(
            selected_doc,
            query
        )

        chat.insert(
            tk.END,
            "\n🧭 Navigation mission generated.\n"
        )

    chat.see(tk.END)

# ---------------------------------------------------
# INTERFAZ
# ---------------------------------------------------

root = tk.Tk()

root.title("ATA ART KEEP - Museum Assistant")
root.geometry("950x700")
root.configure(bg="#1e1e1e")

titulo = tk.Label(
    root,
    text="ATA ART KEEP - Museum Guide",
    font=("Arial", 20, "bold"),
    bg="#1e1e1e",
    fg="white"
)

titulo.pack(pady=10)

chat = ScrolledText(
    root,
    wrap=tk.WORD,
    font=("Consolas", 12),
    bg="#252526",
    fg="white",
    insertbackground="white"
)

chat.pack(
    padx=10,
    pady=10,
    fill=tk.BOTH,
    expand=True
)

chat.insert(
    tk.END,
    "🤖 TIAGo:\n"
    "Welcome to the museum. "
    "How can I assist you today?\n"
)

frame_input = tk.Frame(
    root,
    bg="#1e1e1e"
)

frame_input.pack(
    fill=tk.X,
    padx=10,
    pady=10
)

entrada = tk.Entry(
    frame_input,
    font=("Arial", 13),
    bg="#333333",
    fg="white",
    insertbackground="white"
)

entrada.pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True,
    padx=(0, 10)
)

boton = tk.Button(
    frame_input,
    text="Send",
    command=procesar_consulta,
    bg="#007acc",
    fg="white",
    font=("Arial", 12, "bold")
)

boton.pack(side=tk.RIGHT)

entrada.bind(
    "<Return>",
    lambda event: procesar_consulta()
)

root.mainloop()