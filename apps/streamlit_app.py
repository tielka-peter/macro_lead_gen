import streamlit as st
import pandas as pd
import sys
import os
# add ../src to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import macro_lead_gen as mg


st.title("Macro Lead Gen")

# password since it's a public app
password = st.text_input("Enter Password")
if password == "T13lka":
    st.session_state.clear()
    
    
    # lead gen
    suburb = st.text_input("Enter Suburb")
    num_leads = int(st.number_input("Number of Leads", min_value=1, max_value=60))
    
    if suburb and num_leads:
        df = mg.cafes_for_suburb("West End", max_leads=num_leads)
        
        st.download_button("Download Leads as CSV", df.to_csv(index=False), "leads.csv", "text/csv")
        
        df




