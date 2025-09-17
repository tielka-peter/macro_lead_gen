import sys
import os
# add ../src to the module search path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
import macro_lead_gen as mg
import streamlit as st
import pandas as pd
import math


# initialize session state variables
if "i" not in st.session_state:
    st.session_state.i = 0
if "df" not in st.session_state:
    st.session_state.df = pd.DataFrame()


# make columns
st.set_page_config(layout="wide")
col1, col2, col3 = st.columns([0.2, 0.4, 0.4], gap="large")
col1.title("Inputs")
col2.title("Filtering")
col3.title("Final Outputs")


# column 1 inputs
col1.subheader("Mandatory Inputs")
suburb = col1.text_input("Enter Suburb")
num_leads = int(col1.number_input("Number of Leads", min_value=1, max_value=60))
return_format = col1.selectbox("Return Format", options=["raw", "capsule"], index=0) # temporary

col1.subheader("Optional Filters")
state = col1.text_input("Enter State (e.g. VIC)").strip().upper()
descriptor = col1.text_input("Enter Descriptor (e.g. 'fancy', 'affluent', 'bakery' ect.)").strip()

# search button
col1.write("")
search = col1.button("Search")
if search:
    st.session_state.i = 0
    
    if suburb and num_leads:
        kwargs = {"suburb": suburb, "max_leads": num_leads}
        if state:
            kwargs["state"] = state
        if descriptor:
            kwargs["descriptor"] = descriptor
        if return_format == "capsule":
            kwargs["return_format"] = "capsule"
        
        st.session_state.df = mg.cafes_for_suburb(**kwargs) 
    
    else:
        col1.error("Please enter a suburb and number of leads.")


# column 2 filtering
col21, col22, col2spacer = col2.columns([0.2, 0.15, 0.65])
if col22.button("Next"):
    st.session_state.i += 1
if col21.button("Previous"):
    st.session_state.i += -1
st.session_state.i = max(0, min(st.session_state.i, len(st.session_state.df)-1))    

if isinstance(st.session_state.df, pd.DataFrame) and not st.session_state.df.empty:
    row = st.session_state.df.iloc[st.session_state.i]
    row.name = f"Cafe {st.session_state.i + 1}" 
    
    rating = row.rating
    num_ratings = row.rating_count
    stars = "⭐" * math.floor(rating) + "☆" * (5 - math.floor(rating))
    rating_w_stars = f"{rating} {stars}"
    
    filter_info = pd.Series({"Name": row.place_name, "Address": row.formatted_address, "Rating": rating_w_stars, "Number of Ratings": num_ratings})
    col2.table(filter_info)
    
    col2.link_button("Go to cafe website", row.website)

    
    
    
else:       
    col2.info("No results loaded yet.")
    
    
