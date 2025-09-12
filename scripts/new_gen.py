import pandas as pd
from datetime import date

filename = input("SHARED FILENAME: ").replace(" ", "_").lower()
today = date.today()

input_filename = f"{filename}_{today}.xlsx"
output_filename = f"{filename}_cafes_{today}.xlsx"
input_path = r"C:\Users\peter\OneDrive\Projects\work\macro_lead_gen\data\input"
output_path = r"C:\Users\peter\OneDrive\Projects\work\macro_lead_gen\data\output"
input_filepath = fr"{input_path}\{input_filename}"
output_filepath = fr"{output_path}\{output_filename}"

empty_frame = pd.DataFrame(columns=[""])
empty_frame.to_excel(input_filepath, index=False)
empty_frame.to_excel(output_filepath, index=False)


