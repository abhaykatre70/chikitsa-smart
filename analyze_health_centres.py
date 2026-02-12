import pandas as pd
import os

FILE_PATH = "ogd_health_centres.csv"

def analyze():
    print("Running Health Centres Analysis...")
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found.")
        return
    
    if os.path.getsize(FILE_PATH) == 0:
        print(f"Warning: {FILE_PATH} is empty. Please add data to run analysis.")
        return

    try:
        df = pd.read_csv(FILE_PATH)
        print("\nDataset Overview:")
        print(df.info())
        print("\nFirst 5 rows:")
        print(df.head())
        
        # Basic analysis based on common OGD columns (adjust if needed)
        # Assuming columns like 'State', 'District', 'Facility Name', 'Facility Type'
        
        if 'State' in df.columns:
            print("\nDistribution by State:")
            print(df['State'].value_counts().head(10))
            
        if 'Facility Type' in df.columns:
             print("\nDistribution by Facility Type:")
             print(df['Facility Type'].value_counts().head(10))
        
        if 'District' in df.columns:
            print("\nTop 10 Districts with most facilities:")
            print(df['District'].value_counts().head(10))

    except Exception as e:
        print(f"An error occurred during analysis: {e}")

if __name__ == "__main__":
    analyze()
