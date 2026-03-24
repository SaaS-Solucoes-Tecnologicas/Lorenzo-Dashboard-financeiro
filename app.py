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
            
        # O Python agora vai procurar o nome da planilha no Cofre!
        nome_planilha = st.secrets["cliente"]["planilha"]
        planilha = gc.open(nome_planilha)
        return planilha.worksheet('LANÇAMENTOS')

    aba_lancamentos = conectar_planilha()

    # 3. Pega os dados
    dados = aba_lancamentos.get_all_records()
    
    # Transforma dados em uma tabela inteligente do Pandas e prepara os dados
    if dados:
        df = pd.DataFrame(dados)
        
        # MÁGICA 1: Guarda o número da linha original do Google Sheets
        df['Linha_Planilha'] = df.index + 2 
        
        # MÁGICA 2: Limpa os valores em dinheiro logo no começo para todo o app usar
        if 'Valor' in df.columns:
            def limpar_moeda(v):
                if isinstance(v, (int, float)):
                    return float(v)
                v = str(v).replace('R$', '').strip()
                if ',' in v:
                    v = v.replace('.', '')
                    v = v.replace(',', '.')
                try:
                    return float(v)
                except ValueError:
                    return 0.0
            df['Valor'] = df['Valor'].apply(limpar_moeda)
            
    else:
        df = pd.DataFrame(columns=["Data", "Tipo", "Valor", "Categoria", "Descrição", "Linha_Planilha"])

    # --- FILTRO DE DATA (SIDEBAR) ---
    if not df.empty and 'Data' in df.columns:
        df['Data_Convertida'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        df['Mês/Ano'] = df['Data_Convertida'].dt.strftime('%m/%Y')
        
        st.sidebar.title("🔍 Filtros")
        lista_meses = df['Mês/Ano'].dropna().unique().tolist()
        
        meses_selecionados = st.sidebar.multiselect(
            "Selecione o Mês/Ano:",
            options=lista_meses,
            default=lista_meses
        )
        
        if meses_selecionados:
            df = df[df['Mês/Ano'].isin(meses_selecionados)]


    # =====================================================================
    # CRIANDO AS ABAS DA INTERFACE
    # =====================================================================
    st.divider()
    tab1, tab2 = st.tabs(["📊 Dashboard e Lançamentos", "✏️ Editar / Excluir"])

    # =====================================================================
    # ABA 1: VISUALIZAÇÃO E INSERÇÃO (Seu código original indentado aqui)
    # =====================================================================
    with tab1:
        st.subheader("📊 Resumo Financeiro")

        if not df.empty:
            # 2. Calcular os totais
            total_receitas = df[df['Tipo'] == 'Receita']['Valor'].sum()
            total_despesas = df[df['Tipo'] == 'Despesa']['Valor'].sum()
            total_reservas = df[df['Tipo'] == 'Reserva']['Valor'].sum()
            
            saldo_atual = total_receitas - total_despesas - total_reservas
            
            # 3. Mostrar os "Cards"
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(label="💰 Receitas", value=f"R$ {total_receitas:,.2f}")
            col2.metric(label="💸 Despesas", value=f"R$ {total_despesas:,.2f}")
            col3.metric(label="🏦 Guardado (Reserva)", value=f"R$ {total_reservas:,.2f}")
            col4.metric(label="💳 Saldo Disponível", value=f"R$ {saldo_atual:,.2f}")
            
            # 4. Gráfico de Pizza
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
        df_exibicao = df.drop(columns=['Data_Convertida', 'Mês/Ano', 'Linha_Planilha'], errors='ignore')

        st.dataframe(
            df_exibicao, 
            use_container_width=True,
            column_config={
                "Valor": st.column_config.NumberColumn(
                    "Valor",
                    format="R$ %.2f" 
                )
            }
        )

        st.divider() 

        # Formulário para adicionar novos lançamentos
        st.subheader("➕ Adicionar Novo Lançamento")
        with st.form("form_novo_lancamento", clear_on_submit=True):
            col1, col2, col3 = st.columns(3) 
            
            with col1:
                data = st.date_input("Data")
                tipo = st.selectbox("Tipo", ["Receita", "Despesa", "Reserva"])
            with col2:
                categoria = st.selectbox("Categoria", ["Alimentação", "Transporte", "Moradia", "Lazer", "Salário", "Outros", "Trabalho", "Cofrinho", "Gasolina", "Projetos pess", "Supérfluo", "Cartão", "Assinatura"])
                valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            with col3:
                descricao = st.text_input("Descrição")
                
            submit = st.form_submit_button("Salvar Lançamento")
            
            if submit:
                nova_linha = [
                    data.strftime("%d/%m/%Y"), 
                    tipo,
                    valor, 
                    categoria,  
                    descricao
                ]
                aba_lancamentos.append_row(nova_linha)
                st.success("Lançamento salvo com sucesso!")
                
        st.write("") 
        if st.button("🔄 Atualizar Tabela e Gráficos"):
            st.rerun()

    # =====================================================================
    # ABA 2: EDITAR E EXCLUIR (A Nova Funcionalidade CRUD)
    # =====================================================================
    with tab2:
        st.subheader("✏️ Editar ou Excluir Lançamento")
        
        if not df.empty:
            # 1. Cria um "dicionário" ligando o número da linha ao texto limpo
            mapa_lancamentos = {}
            for index, row in df.iterrows():
                # O texto que vai aparecer na tela (sem o "Linha X:")
                texto_exibicao = f"{row['Data']} - {row['Descrição']} (R$ {row['Valor']:.2f})"
                # Guarda o número da linha como a "chave" invisível
                mapa_lancamentos[row['Linha_Planilha']] = texto_exibicao
            
            # 2. O selectbox mostra o texto, mas devolve o número da linha para o Python!
            linha_alvo = st.selectbox(
                "Selecione o lançamento que deseja alterar:", 
                options=list(mapa_lancamentos.keys()),
                format_func=lambda x: mapa_lancamentos[x]
            )
            
            if linha_alvo:
                # Busca os dados originais dessa linha no nosso DataFrame
                dados_linha = df[df['Linha_Planilha'] == linha_alvo].iloc[0]
                
                st.write("---")
                st.markdown("**Altere os dados abaixo e salve, ou exclua o registro permanentemente:**")
                
               
                # Monta os campos de input já preenchidos com os dados antigos
                col_ed1, col_ed2, col_ed3 = st.columns(3)
                
                with col_ed1:
                    # Tenta converter a data de texto para o calendário
                    try:
                        data_antiga = datetime.strptime(dados_linha['Data'], "%d/%m/%Y").date()
                    except:
                        data_antiga = datetime.today().date()
                        
                    novo_data = st.date_input("Nova Data", value=data_antiga, key="ed_data")
                    
                    # Acha o índice correto do tipo para preencher a caixa
                    tipos_disp = ["Receita", "Despesa", "Reserva"]
                    idx_tipo = tipos_disp.index(dados_linha['Tipo']) if dados_linha['Tipo'] in tipos_disp else 0
                    novo_tipo = st.selectbox("Novo Tipo", tipos_disp, index=idx_tipo, key="ed_tipo")
                    
                with col_ed2:
                    cat_disp = ["Alimentação", "Transporte", "Moradia", "Lazer", "Salário", "Outros", "Trabalho", "Cofrinho", "Gasolina", "Projetos pess", "Supérfluo", "Cartão", "Assinatura"]
                    idx_cat = cat_disp.index(dados_linha['Categoria']) if dados_linha['Categoria'] in cat_disp else 5 # 5 é o index de 'Outros'
                    novo_categoria = st.selectbox("Nova Categoria", cat_disp, index=idx_cat, key="ed_cat")
                    
                    novo_valor = st.number_input("Novo Valor (R$)", min_value=0.0, value=float(dados_linha['Valor']), format="%.2f", key="ed_valor")
                    
                with col_ed3:
                    novo_descricao = st.text_input("Nova Descrição", value=dados_linha['Descrição'], key="ed_desc")
                    
                # Botões de Ação
                st.write("")
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if st.button("💾 Salvar Alterações", use_container_width=True):
                        # Prepara a nova linha formatada
                        linha_atualizada = [
                            novo_data.strftime("%d/%m/%Y"), 
                            novo_tipo,
                            novo_valor, 
                            novo_categoria,  
                            novo_descricao
                        ]
                        # Substitui as células da coluna A até E na linha exata
                        intervalo = f'A{linha_alvo}:E{linha_alvo}'
                        aba_lancamentos.update(range_name=intervalo, values=[linha_atualizada])
                        st.success("Lançamento atualizado com sucesso!")
                        st.rerun() # Recarrega para mostrar o novo valor
                        
                with col_btn2:
                    if st.button("🗑️ Excluir Lançamento", type="primary", use_container_width=True):
                        # Deleta a linha inteira da planilha
                        aba_lancamentos.delete_rows(linha_alvo)
                        st.warning("Lançamento excluído permanentemente!")
                        st.rerun() # Recarrega para remover da tabela

        else:
            st.info("Não há lançamentos registrados para editar.")
