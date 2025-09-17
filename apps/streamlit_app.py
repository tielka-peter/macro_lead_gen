import sys
import os
# add ../src to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import macro_lead_gen as mg
import streamlit as st
import pandas as pd


# page formatting
st.title("Macro Lead Gen")


# input fields
suburb = st.text_input("Enter Suburb")
state = st.text_input("Enter State (optional) e.g. VIC").strip().upper()
descriptor = st.text_input("Enter Descriptor (optional) e.g. 'fancy', 'affluent', 'bakery' ect.").strip()
num_leads = int(st.number_input("Number of Leads", min_value=1, max_value=60))
return_format = st.selectbox("Return Format", options=["raw", "capsule"], index=0)


# search button
if st.button("Search"):
    if suburb and num_leads:
        
        kwargs = {"suburb": suburb, "max_leads": num_leads}
        if state:
            kwargs["state"] = state
        if descriptor:
            kwargs["descriptor"] = descriptor
        if return_format == "capsule":
            kwargs["return_format"] = "capsule"
        
        df = mg.cafes_for_suburb(**kwargs) 
    
        #st.download_button("Download Leads as CSV", df.to_csv(index=False), "leads.csv", "text/csv")
        df
    else:
        st.error("Please enter a suburb and number of leads.")
        
        
    for row in df.itertuples():
        st.write(row.rating)



