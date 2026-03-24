import streamlit as st
import gspread
import pandas as pd
from datetime import datetime
import plotly.express as px
import json 

# 1. Configuração inicial da página (DEVE ser o primeiro comando do app)
st.set_page_config(page_title="Meu Controle Financeiro", layout="wide")

# --- SISTEMA DE LOGIN ---
def check_password():
    """Retorna True se o usuário tiver a senha correta."""
    # Se já estiver logado na sessão, passa direto
    if "password_correct" in st.session_state and st.session_state["password_correct"]:
        return True

    # Se não estiver logado, mostra a tela de login
    st.title("🔒 Acesso Restrito")
    st.write("Por favor, faça login para acessar o painel financeiro.")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        # Puxa o usuário e senha lá do nosso Cofre (Secrets)
        if usuario == st.secrets["login"]["usuario"] and senha == st.secrets["login"]["senha"]:
            st.session_state["password_correct"] = True
            st.rerun() # Atualiza a página agora logado
        else:
            st.error("Usuário ou senha incorretos.")
            return False
    return False

# =====================================================================
# O SEU APLICATIVO REAL SÓ APARECE SE A SENHA ESTIVER CORRETA
# =====================================================================
if check_password():
    
    st.title("Olá, Lorenzo! 👋")
    st.subheader("Seu Dashboard Financeiro")

    # 2. Conecta com o Google Sheets
    @st.cache_resource
    def conectar_planilha():
        # Verifica se estamos na nuvem (onde os 'secrets' existem)
        if "google_credentials" in st.secrets:
            # Puxa a senha do cofre da nuvem
            credenciais_dict = json.loads(st.secrets["google_credentials"])
            gc = gspread.service_account_from_dict(credenciais_dict)
        else:
            # Puxa a senha do arquivo local (quando rodar no seu PC)
            gc = gspread.service_account(filename='credenciais.json')
            
        planilha = gc.open('DashBoard - Finanças')
        return planilha.worksheet('LANÇAMENTOS')

    aba_lancamentos = conectar_planilha()

    # 3. Pega os dados
    dados = aba_lancamentos.get_all_records()
    
    # Transforma dados em uma tabela inteligente do Pandas
    if dados:
        df = pd.DataFrame(dados)
    else:
        df = pd.DataFrame(columns=["Data", "Tipo", "Valor", "Categoria", "Descriçâo"])

    # --- FILTRO DE DATA (SIDEBAR) ---
    if not df.empty and 'Data' in df.columns:
        # 1. Cria uma coluna de data real nos bastidores (sem mexer na original)
        df['Data_Convertida'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        
        # 2. Extrai o "Mês/Ano" (ex: 03/2026)
        df['Mês/Ano'] = df['Data_Convertida'].dt.strftime('%m/%Y')
        
        # 3. Cria a barra lateral (sidebar) para o filtro
        st.sidebar.title("🔍 Filtros")
        lista_meses = df['Mês/Ano'].dropna().unique().tolist()
        
        # 4. Cria o botão de seleção múltipla na barra lateral
        meses_selecionados = st.sidebar.multiselect(
            "Selecione o Mês/Ano:",
            options=lista_meses,
            default=lista_meses # Por padrão, vem com todos selecionados
        )
        
        # 5. O PULO DO GATO: Filtra a tabela inteira com base na sua escolha
        if meses_selecionados:
            df = df[df['Mês/Ano'].isin(meses_selecionados)]

    # --- RESUMO E GRÁFICOS ---
    st.divider()
    st.subheader("📊 Resumo Financeiro")

    # Só mostra os gráficos se tivermos dados na planilha
    if not df.empty:
        # 1. Tratamento inteligente da coluna 'Valor' (Padrão BR)
        if 'Valor' in df.columns:
            def limpar_moeda(v):
                # Se já for um número puro (veio do app), só garante que é float
                if isinstance(v, (int, float)):
                    return float(v)
                
                # Se for texto (veio formatado do Sheets)
                v = str(v).replace('R$', '').strip()
                
                # Se tem vírgula, assumimos que está no padrão brasileiro (ex: 1.500,50)
                if ',' in v:
                    v = v.replace('.', '')  # Remove o ponto de milhar (fica 1500,50)
                    v = v.replace(',', '.') # Troca a vírgula por ponto (fica 1500.50)
                
                # Converte de volta para número matemático
                try:
                    return float(v)
                except ValueError:
                    return 0.0 # Se tiver algum lixo na célula, vira zero
                    
            # Aplica essa limpeza linha por linha na coluna 'Valor'
            df['Valor'] = df['Valor'].apply(limpar_moeda)
        
        # 2. Calcular os totais
        total_receitas = df[df['Tipo'] == 'Receita']['Valor'].sum()
        total_despesas = df[df['Tipo'] == 'Despesa']['Valor'].sum()
        total_reservas = df[df['Tipo'] == 'Reserva']['Valor'].sum() # <-- Nova linha calculando a poupança
        
        # O Saldo Disponível agora desconta as despesas e o que você já guardou na reserva
        saldo_atual = total_receitas - total_despesas - total_reservas
        
        # 3. Mostrar os "Cards" (Métricas) - Agora divididos em 4 colunas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric(label="💰 Receitas", value=f"R$ {total_receitas:,.2f}")
        col2.metric(label="💸 Despesas", value=f"R$ {total_despesas:,.2f}")
        col3.metric(label="🏦 Guardado (Reserva)", value=f"R$ {total_reservas:,.2f}")
        col4.metric(label="💳 Saldo Disponível", value=f"R$ {saldo_atual:,.2f}")
        
        # 4. Criar um Gráfico de Pizza de Despesas por Categoria
        df_despesas = df[df['Tipo'] == 'Despesa']
        
        if not df_despesas.empty:
            fig_pizza = px.pie(
                df_despesas, 
                values='Valor', 
                names='Categoria', 
                title='Onde estou gastando mais?',
                hole=0.4 
            )
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("Ainda não há despesas registradas para gerar o gráfico.")
    
    else:
        st.warning("Adicione alguns lançamentos para ver o resumo financeiro!")

    # Exibe a tabela na tela
    st.subheader("Lançamentos Recentes")
    
    # Criamos uma versão da tabela sem as colunas de bastidores só para mostrar na tela
    df_exibicao = df.drop(columns=['Data_Convertida', 'Mês/Ano'], errors='ignore')

    st.dataframe(
        df_exibicao, # <-- Atenção: mudei de df para df_exibicao aqui!
        use_container_width=True,
        column_config={
            "Valor": st.column_config.NumberColumn(
                "Valor",
                format="R$ %.2f" 
            )
        }
    )

    st.divider() # Cria uma linha separadora

    # Formulário para adicionar novos lançamentos
    st.subheader("➕ Adicionar Novo Lançamento")
    with st.form("form_novo_lancamento", clear_on_submit=True):
        col1, col2, col3 = st.columns(3) # Divide a tela em 3 colunas
        
        with col1:
            data = st.date_input("Data")
            tipo = st.selectbox("Tipo", ["Receita", "Despesa", "Reserva"])
        with col2:
            categoria = st.selectbox("Categoria", ["Alimentação", "Transporte", "Moradia", "Lazer", "Salário", "Outros", "Trabalho", "Cofrinho", "Gasolina", "Projetos pess", "Supérfluo", "Cartão", "Assinatura"])
            valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
        with col3:
            descricao = st.text_input("Descrição")
            
        # Botão de salvar
        submit = st.form_submit_button("Salvar Lançamento")
        
        if submit:
            # Prepara a linha com as informações digitadas
            nova_linha = [
                data.strftime("%d/%m/%Y"), 
                tipo,
                valor, 
                categoria,  
                descricao
            ]
            # Envia para o Google Sheets
            aba_lancamentos.append_row(nova_linha)
            st.success("Lançamento salvo com sucesso!")
    st.write("") # Dá um espacinho em branco
    if st.button("🔄 Atualizar Tabela e Gráficos"):
        st.rerun()
