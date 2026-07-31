import streamlit as st
from supabase import create_client
from google import genai

# Configuração da página para Mobile e Tablet
st.set_page_config(
    page_title="CPCON Concursos - Questões",
    page_icon="🎯",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Customização CSS para Interface
st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }
    
    .questao-header {
        background: #1E2640;
        padding: 12px 16px;
        border-radius: 10px;
        border-left: 4px solid #4F46E5;
        margin-bottom: 12px;
    }
    
    .questao-meta {
        color: #9CA3AF;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0;
    }
    
    .enunciado-card {
        background: #161B22;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #30363D;
        font-size: 1.05rem;
        line-height: 1.6;
        color: #F3F4F6;
        margin-bottom: 16px;
        white-space: pre-line;
    }

    div.stButton > button {
        width: 100%;
        padding: 14px 16px !important;
        font-size: 0.98rem !important;
        border-radius: 10px !important;
        margin-bottom: 6px;
        text-align: left !important;
        justify-content: flex-start !important;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# Conexões com o Supabase e com a API do Gemini
@st.cache_resource
def init_services():
    supabase_client = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )
    gemini_client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    return supabase_client, gemini_client

supabase, gemini = init_services()

# Coleta de dados para os Filtros
@st.cache_data(ttl=300)
def carregar_opcoes_filtros():
    try:
        materias = [r['materia'] for r in supabase.table("questoes_cpcon").select("materia").execute().data]
        cargos = [r['cargo'] for r in supabase.table("questoes_cpcon").select("cargo").execute().data]
        anos = [r['ano'] for r in supabase.table("questoes_cpcon").select("ano").execute().data]
        return {
            "materias": sorted(list(set(materias))),
            "cargos": sorted(list(set(cargos))),
            "anos": sorted(list(set(anos)), reverse=True)
        }
    except Exception:
        return {"materias": [], "cargos": [], "anos": []}

opcoes = carregar_opcoes_filtros()

# Painel de Filtros Recolhível
with st.expander("⚙️ **Filtros de Busca**", expanded=False):
    f_materia = st.selectbox("Matéria:", ["Todas"] + opcoes["materias"])
    f_cargo = st.selectbox("Cargo:", ["Todos"] + opcoes["cargos"])
    f_ano = st.selectbox("Ano:", ["Todos"] + opcoes["anos"])

    if st.button("Aplicar Filtros", type="primary"):
        st.session_state.questao_atual = None
        st.session_state.respondido = False
        st.session_state.opcao_marcada = None
        st.session_state.explicacao_ia = None
        st.rerun()

# Consulta com base nos Filtros
def buscar_questao():
    query = supabase.table("questoes_cpcon").select("*")
    if f_materia != "Todas": query = query.eq("materia", f_materia)
    if f_cargo != "Todos": query = query.eq("cargo", f_cargo)
    if f_ano != "Todos": query = query.eq("ano", int(f_ano))
    
    res = query.limit(1).execute()
    return res.data[0] if res.data else None

# Controle de Estados na Sessão
if "questao_atual" not in st.session_state or st.session_state.questao_atual is None:
    st.session_state.questao_atual = buscar_questao()
if "respondido" not in st.session_state:
    st.session_state.respondido = False
if "opcao_marcada" not in st.session_state:
    st.session_state.opcao_marcada = None
if "explicacao_ia" not in st.session_state:
    st.session_state.explicacao_ia = None

q = st.session_state.questao_atual

if q:
    # Cabeçalho Informativo
    st.markdown(f"""
        <div class="questao-header">
            <p class="questao-meta">📍 {q['concurso']} ({q['ano']}) — {q['cargo']}</p>
            <p class="questao-meta" style="color: #6366F1;">📚 {q['materia']}</p>
        </div>
    """, unsafe_allow_html=True)

    # Exibição do Enunciado Completo
    st.markdown(
        f"""
        <div class="enunciado-card">
            <span style="color: #6366F1; font-weight: bold; font-size: 0.9rem;">ENUNCIADO DA QUESTÃO #{q['id']}</span>
            <br><br>
            {q['enunciado']}
        </div>
        """, 
        unsafe_allow_html=True
    )

    alts = {
        "A": q["alternativa_a"],
        "B": q["alternativa_b"],
        "C": q["alternativa_c"],
        "D": q["alternativa_d"],
        "E": q["alternativa_e"]
    }

    # Renderização das Alternativas
    for letra, texto in alts.items():
        if not texto: continue
        
        btn_type = "secondary"
        label = f"{letra}) {texto}"

        if st.session_state.respondido:
            if letra == q["gabarito"]:
                label = f"✅ {letra}) {texto}"
                btn_type = "primary"
            elif letra == st.session_state.opcao_marcada:
                label = f"❌ {letra}) {texto}"

        if st.button(label, key=f"btn_{letra}", type=btn_type, disabled=st.session_state.respondido):
            st.session_state.opcao_marcada = letra
            st.session_state.respondido = True
            st.rerun()

    # Processamento e Explicação da IA
    if st.session_state.respondido:
        st.write("")
        if st.session_state.opcao_marcada == q["gabarito"]:
            st.success("🎉 **Resposta Correta!**")
        else:
            st.error(f"❌ **Resposta Incorreta.** O gabarito oficial é a letra **{q['gabarito']}**.")

        if not st.session_state.explicacao_ia:
            with st.spinner("🤖 O Professor Virtual está analisando a questão..."):
                prompt = f"""
                Você é um professor especialista em concursos públicos da banca CPCON.
                Sua tarefa é analisar a questão abaixo e fornecer uma explicação completa para o aluno.

                DADOS DA QUESTÃO:
                - Banca: CPCON
                - Matéria: {q['materia']}
                - Cargo: {q['cargo']}
                - Enunciado Completo: {q['enunciado']}
                - Alternativas:
                  A) {q['alternativa_a']}
                  B) {q['alternativa_b']}
                  C) {q['alternativa_c']}
                  D) {q['alternativa_d']}
                  E) {q['alternativa_e']}
                - Gabarito Oficial Correto: {q['gabarito']}
                - Alternativa que o aluno marcou: {st.session_state.opcao_marcada}

                FORMATO DA SUA RESPOSTA (Use Markdown legível para tela de celular):
                
                📌 **Por que a alternativa {q['gabarito']} é a CORRETA?**
                (Explique o raciocínio passo a passo ou cite a lei/regra que fundamenta a resposta).

                💡 **Como chegar a essa conclusão (Passo a Passo):**
                (Mostre a linha de raciocínio lógico que o candidato deveria seguir na hora da prova).

                🚫 **Por que as outras estão ERRADAS?**
                (Aponta brevemente o erro de cada uma das outras alternativas não gabaritadas).
                """
                res = gemini.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt
                )
                st.session_state.explicacao_ia = res.text

        with st.expander("💡 **Resolução Guiada & Explicação da IA**", expanded=True):
            st.markdown(st.session_state.explicacao_ia)

        if st.button("Próxima Questão ➡️", type="primary"):
            st.session_state.questao_atual = buscar_questao()
            st.session_state.respondido = False
            st.session_state.opcao_marcada = None
            st.session_state.explicacao_ia = None
            st.rerun()
else:
    st.info("Nenhuma questão encontrada para os filtros selecionados.")
