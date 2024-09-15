import streamlit as st
import pandas as pd
import plotly.express as px

if 'messages' not in st.session_state:
    st.session_state.messages = []

st.title("Data Dashboard")
st.write("Collabse Open ESG reporting")

# Sample data (In a real app, you would fetch this from a database)
data = {
    'Company Name': ['Company A', 'Company B', 'Company C', 'Company D', 'Company E'],
    'Location': ['USA', 'Canada', 'USA', 'Germany', 'Canada'],
    'Company Size': ['Large', 'Medium', 'Small', 'Large', 'Medium'],
    'Industry': ['Manufacturing', 'Retail', 'Fishing', 'Technology', 'Finance'],
    'ESG Score': [75, 85, 65, 90, 80],
    'CSR Score': [80, 70, 60, 95, 85],
}
df = pd.DataFrame(data)

# Filters
st.sidebar.subheader("Filter Data")
selected_location = st.sidebar.multiselect(
    "Select Location(s)",
    options=df['Location'].unique(),
    default=df['Location'].unique()
)
selected_size = st.sidebar.multiselect(
    "Select Company Size(s)",
    options=df['Company Size'].unique(),
    default=df['Company Size'].unique()
)
selected_industry = st.sidebar.multiselect(
    "Select Industry(ies)",
    options=df['Industry'].unique(),
    default=df['Industry'].unique()
)

# Filter dataframe
filtered_df = df[
    (df['Location'].isin(selected_location)) &
    (df['Company Size'].isin(selected_size)) &
    (df['Industry'].isin(selected_industry))
]

st.write("### Filtered Data")
st.dataframe(filtered_df)

# Create graphs
st.write("### ESG Scores")
fig_esg = px.bar(
    filtered_df,
    x='Company Name',
    y='ESG Score',
    color='Industry',
    barmode='group',
    title="ESG Scores by Company"
)
st.plotly_chart(fig_esg, use_container_width=True)

st.write("### CSR Scores")
fig_csr = px.bar(
    filtered_df,
    x='Company Name',
    y='CSR Score',
    color='Industry',
    barmode='group',
    title="CSR Scores by Company"
)
st.plotly_chart(fig_csr, use_container_width=True)