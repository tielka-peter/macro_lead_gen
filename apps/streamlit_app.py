import sys
import os

# add ../src to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import macro_lead_gen as mg
import streamlit as st
import pandas as pd


st.title("Macro Lead Gen")

suburb = st.text_input("Enter Suburb")
state = st.text_input("Enter State, e.g. VIC (Optional)").strip().upper()
num_leads = int(st.number_input("Number of Leads", min_value=1, max_value=60))

if st.button("Search"):
    if suburb and num_leads:
        
        kwargs = {"suburb": suburb, "max_leads": num_leads}
        if state:
            kwargs["state"] = state
        
        df = mg.cafes_for_suburb(**kwargs)
        st.download_button("Download Leads as CSV", df.to_csv(index=False), "leads.csv", "text/csv")
        df
    else:
        st.error("Please enter a suburb and number of leads.")



