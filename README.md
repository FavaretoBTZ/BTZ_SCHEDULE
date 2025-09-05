# BTZ Schedule App (Streamlit)

App simples e bonito para cronograma de pista:
- Cadastrar atividades (início, fim, descrição).
- Visualizar como planilha com cores de status (concluída, em execução, próxima, futura).
- Painel com **tempo restante da atividade atual** e **tempo até a próxima**.
- Salvar/Carregar CSV.
- Auto-refresh opcional para atualizar com o relógio do PC.

## Rodar localmente
```bash
# Python 3.10+
pip install -r requirements.txt
streamlit run app.py
```

## Deploy no Streamlit Cloud
1. Faça um fork/clone deste repositório para sua conta.
2. Em https://share.streamlit.io/ selecione o repositório e o arquivo `app.py`.
3. Defina o **Python 3.10+** como runtime (se aplicável).

## CSV
O CSV usa colunas: `Date,Start,End,Activity` (exemplos em `sample_data/cronograma_exemplo.csv`).

## Licença
MIT
