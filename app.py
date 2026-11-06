"""Streamlit web app for the Ask your data assistant. Run with: streamlit run app.py"""
from decimal import Decimal

import pandas as pd
import streamlit as st

from assistant import ask

st.set_page_config(page_title="Ask your data", layout="wide")

EXAMPLES = [
    "What percentage of delivered orders arrived late?",
    "Which 5 customer states have the highest late delivery rate, among states with at least 1,000 delivered orders?",
    "What is the average review score for late orders compared with on-time orders?",
    "What are the top 10 product categories by revenue?",
    "What percentage of customers are repeat customers?",
    "How much revenue was lost to canceled and unavailable orders?",
]


@st.cache_data(ttl=3600, show_spinner=False)
def cached_ask(question):
    """Same question within an hour: reuse the answer instead of calling the model again."""
    return ask(question)


def to_dataframe(columns, rows):
    clean = [[float(v) if isinstance(v, Decimal) else v for v in row] for row in rows]
    return pd.DataFrame(clean, columns=columns)


def show_answer(result):
    st.markdown(f"**{result['question']}**")
    if result["error"]:
        st.error(result["error"])
    else:
        df = to_dataframe(result["columns"], result["rows"])
        if df.shape == (1, 1):
            st.metric(label=df.columns[0].replace("_", " "), value=f"{df.iloc[0, 0]:,}")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
            numeric = df.select_dtypes("number").columns
            if df.shape[1] == 2 and len(numeric) == 1 and 1 < len(df) <= 30:
                st.bar_chart(df.set_index(df.columns[0]))
    if result["sql"]:
        with st.expander("Show the SQL"):
            st.code(result["sql"], language="sql")
            if result["explanation"]:
                st.caption(result["explanation"])
            st.caption(f"Attempts: {result['attempts']}")


st.title("Ask your data")
st.caption("Ask a question in plain English about 100k Brazilian eCommerce orders (Olist, 2017 to 2018). "
           "The answer comes straight from the database, and you can always see the SQL behind it.")

with st.sidebar:
    st.header("How it stays safe")
    st.markdown(
        "- The AI only writes the query. **Every number comes from the database.**\n"
        "- Each query is checked: one SELECT only, no write commands, clean tables only.\n"
        "- It runs as a **read-only** database user that can't change anything.\n"
        "- Queries time out after 10 seconds.\n"
        "- If a query fails, the error goes back to the AI once to fix it."
    )
    st.header("The data")
    st.markdown("Orders, items, customers, products, sellers and reviews from Olist, "
                "modelled as a star schema in PostgreSQL. By default, answers cover Jan 2017 to Aug 2018.")

if "history" not in st.session_state:
    st.session_state.history = []

st.write("Try one:")
columns = st.columns(3)
clicked = None
for i, example in enumerate(EXAMPLES):
    if columns[i % 3].button(example, use_container_width=True):
        clicked = example

typed = st.chat_input("Ask a question about the orders")
question = typed or clicked

if question:
    with st.spinner("Writing and running the query..."):
        st.session_state.history.insert(0, cached_ask(question))

for result in st.session_state.history:
    st.divider()
    show_answer(result)
