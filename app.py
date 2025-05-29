import streamlit as st
import pandas as pd
import plotly.express as px

# --- Page Configuration ---
st.set_page_config(
    page_title="Mansoorah Hospital",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Helper Functions ---

@st.cache_data  # Cache the data loading and processing
def load_data(uploaded_file):
    """Loads data from the uploaded CSV file."""
    try:
        df = pd.read_csv(uploaded_file)
        return df
    except Exception as e:
        st.error(f"Error loading CSV file: {e}")
        return None

def detect_columns(df):
    """
    Enhanced column detection with more flexible matching
    """
    column_map = {}
    
    # Define patterns for each required column
    patterns = {
        'Year': ['year', 'yr', 'years', 'date_year', 'time_year'],
        'Quarter': ['quarter', 'qtr', 'q', 'quarters', 'period'],
        'Department': ['department', 'dept', 'dep', 'ward', 'unit', 'division', 'section'],
        'No. of Patients': ['patients', 'patient', 'count', 'number', 'total', 'num_patients', 'patient_count', 'no_of_patients', 'patient_total']
    }
    
    # Try to match columns
    for target_col, search_terms in patterns.items():
        for col in df.columns:
            col_clean = col.lower().replace(' ', '_').replace('.', '_').replace('-', '_')
            if any(term in col_clean for term in search_terms):
                column_map[target_col] = col
                break
    
    return column_map

def preprocess_data(df):
    """
    Enhanced preprocessing with better column detection and user feedback
    """
   # st.write("**Debug Info - Original Columns:**")
   # st.write(df.columns.tolist())
    
    # Detect columns
    column_map = detect_columns(df)
    #st.write("**Debug Info - Detected Columns:**")
   # st.write(column_map)
    
    # Check what we found
    required_cols = ['Year', 'Quarter', 'Department', 'No. of Patients']
    missing_cols = [col for col in required_cols if col not in column_map]
    
    if missing_cols:
        st.error(f"❌ Could not detect these required columns: {', '.join(missing_cols)}")
        st.write("**Available columns in your CSV:**")
        for i, col in enumerate(df.columns):
            st.write(f"{i+1}. `{col}`")
        
        st.write("**Manual Column Mapping:**")
        st.write("Please help map your columns to the required fields:")
        
        manual_map = {}
        for req_col in required_cols:
            if req_col in column_map:
                continue
            
            options = ['None'] + df.columns.tolist()
            selected = st.selectbox(
                f"Select column for '{req_col}':",
                options=options,
                key=f"map_{req_col}"
            )
            if selected != 'None':
                manual_map[req_col] = selected
        
        # Combine detected and manual mappings
        column_map.update(manual_map)
        
        # Check again
        missing_cols = [col for col in required_cols if col not in column_map or column_map[col] is None]
        if missing_cols:
            st.warning(f"Still missing: {', '.join(missing_cols)}. Cannot proceed with analysis.")
            return None
    
    # Rename columns based on mapping
    rename_dict = {v: k for k, v in column_map.items() if v is not None}
    df_renamed = df.rename(columns=rename_dict)
    
    try:
        # Convert 'No. of Patients' to numeric, handling various formats
        if 'No. of Patients' in df_renamed.columns:
            patient_col = df_renamed['No. of Patients']
            if patient_col.dtype == 'object':
                # Handle various string formats
                patient_col = patient_col.astype(str).str.replace(',', '', regex=False)
                patient_col = patient_col.str.replace(' ', '', regex=False)
                patient_col = pd.to_numeric(patient_col, errors='coerce')
                df_renamed['No. of Patients'] = patient_col
            
            # Remove rows where conversion failed
            df_renamed = df_renamed.dropna(subset=['No. of Patients'])
            
            if df_renamed.empty:
                st.error("No valid patient numbers found after conversion!")
                return None

        # Standardize Quarter
        if 'Quarter' in df_renamed.columns:
            quarter_col = df_renamed['Quarter'].astype(str).str.upper()
            # Handle various quarter formats
            quarter_col = quarter_col.str.replace('QUARTER', 'Q', regex=False)
            quarter_col = quarter_col.str.replace(' ', '', regex=False)
            
            # Convert numbers to Q format
            def standardize_quarter(q):
                q = str(q).strip().upper()
                if q in ['1', '1ST', 'FIRST']:
                    return 'Q1'
                elif q in ['2', '2ND', 'SECOND']:
                    return 'Q2'
                elif q in ['3', '3RD', 'THIRD']:
                    return 'Q3'
                elif q in ['4', '4TH', 'FOURTH']:
                    return 'Q4'
                elif q.startswith('Q') and q[1:].isdigit():
                    return q
                else:
                    return q
            
            df_renamed['Quarter'] = quarter_col.apply(standardize_quarter)
            
            # Create categorical for proper sorting
            valid_quarters = ['Q1', 'Q2', 'Q3', 'Q4']
            df_renamed = df_renamed[df_renamed['Quarter'].isin(valid_quarters)]
            df_renamed['Quarter'] = pd.Categorical(df_renamed['Quarter'], categories=valid_quarters, ordered=True)

        # Convert Year to string for categorical treatment
        if 'Year' in df_renamed.columns:
            df_renamed['Year'] = df_renamed['Year'].astype(str)

        # Clean Department names
        if 'Department' in df_renamed.columns:
            df_renamed['Department'] = df_renamed['Department'].astype(str).str.strip()

    except Exception as e:
        st.error(f"Error during data preprocessing: {e}")
       # st.write("**Debug - Data types:**")
        st.write(df_renamed.dtypes)
        return None

    st.success(f"✅ Successfully processed {len(df_renamed)} rows of data!")
    return df_renamed

# --- App Layout and Logic ---

st.title("🏥 Mansoorah Hospital Patient Influx Analysis")
st.markdown("""
Welcome!  
This tool helps you visualize patient data from your CSV file.  
Upload your file, select a department, and see how patient numbers compare across quarters and years.
""")

# --- Sidebar for Upload and Controls ---

with st.sidebar:
    st.header("⚙️ Controls")
    uploaded_file = st.file_uploader("Upload your CSV file", type=["csv"])
    
    if uploaded_file:
        st.write("**File Info:**")
        st.write(f"Name: {uploaded_file.name}")
        st.write(f"Size: {uploaded_file.size} bytes")

selected_department = None
df_processed = None

if uploaded_file:
    df_raw = load_data(uploaded_file)

    if df_raw is not None:
        st.write(f"**Raw data shape:** {df_raw.shape[0]} rows × {df_raw.shape[1]} columns")
        
        # Show first few rows for debugging
        with st.expander("🔍 Preview Raw Data"):
            st.dataframe(df_raw.head())
        
        df_processed = preprocess_data(df_raw.copy())

        if df_processed is not None and not df_processed.empty:
            if 'Department' in df_processed.columns:
                departments = sorted(df_processed['Department'].astype(str).unique())
                st.write(f"**Available Departments:** {len(departments)}")

                selected_department = st.selectbox(
                    "Select Department:",
                    options=departments,
                    help="Choose the department to analyze."
                )
            else:
                st.warning("The 'Department' column is missing from your CSV. Please ensure it's included.")
                selected_department = None
        else:
            st.info("Data processing incomplete. Please check the column mappings above.")
            selected_department = None
    else:
        selected_department = None
else:
    st.info("👈 Please upload a CSV file using the sidebar to get started.")
    selected_department = None
    df_processed = None

# --- Main Panel for Displaying Charts and Data ---

if uploaded_file and df_processed is not None and not df_processed.empty and selected_department:
    st.header(f"📊 Patient Influx Analysis: {selected_department}")

    # Filter data for the selected department
    department_df = df_processed[df_processed['Department'] == selected_department]

    if not department_df.empty:
        # Display some stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Patients", f"{department_df['No. of Patients'].sum():,}")
        with col2:
            st.metric("Time Period", f"{department_df['Year'].nunique()} years")
        with col3:
            st.metric("Data Points", len(department_df))

        # Group data for the chart
        chart_data = department_df.groupby(['Year', 'Quarter'], as_index=False, observed=False)['No. of Patients'].sum()
        chart_data = chart_data.sort_values(['Year', 'Quarter'])

        if not chart_data.empty:
            # Create the interactive bar chart
            fig = px.bar(
                chart_data,
                x='Year',
                y='No. of Patients',
                color='Quarter',
                barmode='group',
                title=f"Quarterly Patient Influx for {selected_department}",
                labels={'No. of Patients': 'Number of Patients', 'Year': 'Year', 'Quarter': 'Quarter'},
                height=500,
                color_discrete_map={
                    "Q1": "#1f77b4",
                    "Q2": "#ff7f0e", 
                    "Q3": "#2ca02c",
                    "Q4": "#d62728",
                }
            )
            fig.update_layout(
                xaxis_title="Year",
                yaxis_title="Number of Patients",
                legend_title_text='Quarter',
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

            # Line chart for trends
            fig_line = px.line(
                chart_data,
                x='Year',
                y='No. of Patients',
                color='Quarter',
                title=f"Trend Analysis: {selected_department}",
                markers=True
            )
            st.plotly_chart(fig_line, use_container_width=True)

            # Data table
            with st.expander("📋 View Detailed Data"):
                st.dataframe(
                    chart_data.pivot(index='Year', columns='Quarter', values='No. of Patients').fillna(0),
                    use_container_width=True
                )
        else:
            st.warning(f"No data available for {selected_department} after processing.")
    else:
        st.warning(f"No data found for department: {selected_department}")

elif uploaded_file and (df_processed is None or df_processed.empty):
    st.info("⚠️ Please complete the column mapping above to proceed with the analysis.")

# --- Footer ---
st.markdown("---")
st.markdown("🏥 **Hospital Data Analyzer** | Developed by Usman Zafar")
st.markdown(
    f"<p style='text-align: center; color: grey; font-size: 12px;'>Last updated: {pd.Timestamp.now(tz='Asia/Karachi').strftime('%Y-%m-%d %H:%M:%S %Z')}</p>",
    unsafe_allow_html=True,
)