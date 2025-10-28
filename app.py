"""
Last-Mile Delivery Analytics Dashboard
FA-2: LogiSight Analytics Pvt. Ltd.
Author: Jwal Patel
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Page configuration
st.set_page_config(
    page_title="Last-Mile Delivery Analytics",
    page_icon="🚚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
    }
    .stMetric label {
        color: #2c3e50 !important;
        font-weight: 600 !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #1f77b4 !important;
        font-size: 24px !important;
        font-weight: 700 !important;
    }
    .stMetric [data-testid="stMetricDelta"] {
        color: #555555 !important;
    }
    h1 {
        color: #1f77b4;
        padding-bottom: 20px;
    }
    h2 {
        color: #2c3e50;
        padding-top: 20px;
        padding-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# ==================== DATA LOADING & CLEANING ====================

@st.cache_data(show_spinner=False)
def load_and_clean_data(file_path):
    """
    Load and clean the delivery dataset with comprehensive preprocessing.
    Handles missing values, standardizes categories, and derives new metrics.
    """
    try:
        # Load data
        df = pd.read_excel(file_path, engine='openpyxl')
        
        # Display raw data info for debugging
        original_shape = df.shape
        
        # Standardize column names (handle spaces, case variations)
        df.columns = df.columns.str.strip().str.replace(' ', '_')
        
        # Expected columns with possible variations
        column_mapping = {
            'delivery_time': ['Delivery_Time', 'delivery_time', 'Time', 'DeliveryTime'],
            'traffic': ['Traffic', 'traffic', 'Traffic_Condition'],
            'weather': ['Weather', 'weather', 'Weather_Condition'],
            'vehicle': ['Vehicle', 'vehicle', 'Vehicle_Type'],
            'agent_age': ['Agent_Age', 'agent_age', 'Age'],
            'agent_rating': ['Agent_Rating', 'agent_rating', 'Rating'],
            'area': ['Area', 'area', 'Location', 'Region'],
            'category': ['Category', 'category', 'Product_Category']
        }
        
        # Flexible column detection
        for standard_name, variations in column_mapping.items():
            for col in df.columns:
                if col in variations:
                    df.rename(columns={col: standard_name}, inplace=True)
                    break
        
        # Ensure required columns exist
        required_cols = ['delivery_time', 'traffic', 'weather', 'vehicle', 
                        'agent_age', 'agent_rating', 'area', 'category']
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            st.error(f"Available columns: {df.columns.tolist()}")
            st.stop()
        
        # Data type conversions
        df['delivery_time'] = pd.to_numeric(df['delivery_time'], errors='coerce')
        df['agent_age'] = pd.to_numeric(df['agent_age'], errors='coerce')
        df['agent_rating'] = pd.to_numeric(df['agent_rating'], errors='coerce')
        
        # Handle categorical columns: strip whitespace, title case
        categorical_cols = ['traffic', 'weather', 'vehicle', 'area', 'category']
        for col in categorical_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.title()
                # Remove 'Nan' string values
                df[col] = df[col].replace('Nan', np.nan)
        
        # Drop rows with missing critical values
        df = df.dropna(subset=['delivery_time'])
        
        # Fill remaining missing values strategically
        if df['agent_age'].isnull().sum() > 0:
            df['agent_age'].fillna(df['agent_age'].median(), inplace=True)
        if df['agent_rating'].isnull().sum() > 0:
            df['agent_rating'].fillna(df['agent_rating'].median(), inplace=True)
        
        # For categorical columns, fill with mode or 'Unknown'
        for col in categorical_cols:
            if df[col].isnull().sum() > 0:
                mode_val = df[col].mode()
                if len(mode_val) > 0:
                    df[col].fillna(mode_val[0], inplace=True)
                else:
                    df[col].fillna('Unknown', inplace=True)
        
        # ===== DERIVE NEW METRICS =====
        
        # 1. Late delivery flag: delivery_time > mean + 1 std deviation
        mean_time = df['delivery_time'].mean()
        std_time = df['delivery_time'].std()
        threshold = mean_time + std_time
        df['is_late'] = (df['delivery_time'] > threshold).astype(int)
        
        # 2. Age groups for agent age
        df['age_group'] = pd.cut(df['agent_age'], 
                                 bins=[0, 25, 40, 100], 
                                 labels=['<25', '25-40', '40+'])
        
        # 3. Delivery time categories for better analysis
        df['time_category'] = pd.cut(df['delivery_time'],
                                      bins=[0, 20, 30, 40, np.inf],
                                      labels=['Very Fast (<20)', 'Fast (20-30)', 
                                             'Average (30-40)', 'Slow (>40)'])
        
        cleaned_shape = df.shape
        
        return df, original_shape, cleaned_shape, threshold
        
    except FileNotFoundError:
        st.error("⚠️ Data file not found! Please ensure 'Last mile Delivery Data.xlsx' is in the 'data/' folder.")
        st.stop()
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        st.stop()

# ==================== VISUALIZATION FUNCTIONS ====================

def create_delay_analyzer(df_filtered):
    """
    Compulsory Visual 1: Delay Analyzer showing avg delivery time 
    by Weather and Traffic conditions
    """
    # Aggregate by weather
    weather_agg = df_filtered.groupby('weather').agg({
        'delivery_time': 'mean',
        'is_late': 'mean'
    }).reset_index()
    weather_agg['late_pct'] = weather_agg['is_late'] * 100
    weather_agg = weather_agg.sort_values('delivery_time', ascending=False)
    
    # Aggregate by traffic
    traffic_agg = df_filtered.groupby('traffic').agg({
        'delivery_time': 'mean',
        'is_late': 'mean'
    }).reset_index()
    traffic_agg['late_pct'] = traffic_agg['is_late'] * 100
    traffic_agg = traffic_agg.sort_values('delivery_time', ascending=False)
    
    # Create subplots
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=('Average Delivery Time by Weather', 
                       'Average Delivery Time by Traffic'),
        specs=[[{"secondary_y": True}, {"secondary_y": True}]]
    )
    
    # Weather chart
    fig.add_trace(
        go.Bar(x=weather_agg['weather'], 
               y=weather_agg['delivery_time'],
               name='Avg Time',
               marker_color='lightblue',
               text=weather_agg['delivery_time'].round(1),
               textposition='outside',
               showlegend=True),
        row=1, col=1, secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(x=weather_agg['weather'],
                  y=weather_agg['late_pct'],
                  name='Late %',
                  mode='lines+markers',
                  marker=dict(size=10, color='red'),
                  line=dict(width=2, color='red'),
                  showlegend=True),
        row=1, col=1, secondary_y=True
    )
    
    # Traffic chart
    fig.add_trace(
        go.Bar(x=traffic_agg['traffic'],
               y=traffic_agg['delivery_time'],
               name='Avg Time',
               marker_color='lightgreen',
               text=traffic_agg['delivery_time'].round(1),
               textposition='outside',
               showlegend=False),
        row=1, col=2, secondary_y=False
    )
    
    fig.add_trace(
        go.Scatter(x=traffic_agg['traffic'],
                  y=traffic_agg['late_pct'],
                  name='Late %',
                  mode='lines+markers',
                  marker=dict(size=10, color='red'),
                  line=dict(width=2, color='red'),
                  showlegend=False),
        row=1, col=2, secondary_y=True
    )
    
    # Update axes
    fig.update_yaxes(title_text="Avg Delivery Time (min)", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="% Late Deliveries", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Avg Delivery Time (min)", row=1, col=2, secondary_y=False)
    fig.update_yaxes(title_text="% Late Deliveries", row=1, col=2, secondary_y=True)
    
    fig.update_layout(height=400, showlegend=True, 
                     legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    return fig

def create_vehicle_comparison(df_filtered):
    """
    Compulsory Visual 2: Vehicle Comparison showing avg delivery time by vehicle type
    """
    vehicle_agg = df_filtered.groupby('vehicle').agg({
        'delivery_time': 'mean',
        'is_late': 'mean'
    }).reset_index()
    vehicle_agg['late_pct'] = vehicle_agg['is_late'] * 100
    vehicle_agg = vehicle_agg.sort_values('delivery_time')
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=vehicle_agg['vehicle'],
        y=vehicle_agg['delivery_time'],
        text=vehicle_agg['delivery_time'].round(1),
        textposition='outside',
        marker=dict(
            color=vehicle_agg['delivery_time'],
            colorscale='RdYlGn_r',
            showscale=True,
            colorbar=dict(title="Avg Time")
        ),
        hovertemplate='<b>%{x}</b><br>Avg Time: %{y:.1f} min<br>Late: ' + 
                     vehicle_agg['late_pct'].round(1).astype(str) + '%<extra></extra>'
    ))
    
    fig.update_layout(
        title="Vehicle Performance Comparison",
        xaxis_title="Vehicle Type",
        yaxis_title="Average Delivery Time (minutes)",
        height=400
    )
    
    return fig

def create_agent_performance_scatter(df_filtered):
    """
    Compulsory Visual 3: Agent Performance Scatter Plot
    showing Agent_Rating vs Delivery_Time colored by Age Group
    WITH TRENDLINE
    """
    fig = px.scatter(
        df_filtered,
        x='agent_rating',
        y='delivery_time',
        color='age_group',
        size='delivery_time',
        hover_data=['vehicle', 'area', 'category'],
        title='Agent Performance: Rating vs Delivery Time by Age Group',
        labels={
            'agent_rating': 'Agent Rating',
            'delivery_time': 'Delivery Time (min)',
            'age_group': 'Age Bin'
        },
        color_discrete_sequence=px.colors.qualitative.Set2,
        trendline='ols',  # Add trendline
        trendline_scope='overall'
    )
    
    fig.update_layout(height=450)
    
    return fig

def create_area_heatmap(df_filtered):
    """
    Compulsory Visual 4: Area Heatmap showing avg delivery time across areas
    """
    # Create pivot for heatmap (Area vs Category)
    pivot = df_filtered.pivot_table(
        values='delivery_time',
        index='area',
        columns='category',
        aggfunc='mean'
    )
    
    fig = go.Figure(data=go.Heatmap(
        z=pivot.values,
        x=pivot.columns,
        y=pivot.index,
        colorscale='RdYlGn_r',
        text=np.round(pivot.values, 1),
        texttemplate='%{text}',
        textfont={"size": 10},
        colorbar=dict(title="Avg Time (min)")
    ))
    
    fig.update_layout(
        title='Delivery Time Heatmap: Area × Category',
        xaxis_title='Product Category',
        yaxis_title='Delivery Area',
        height=500
    )
    
    return fig

def create_category_boxplot(df_filtered):
    """
    Compulsory Visual 5: Category Visualizer (Boxplot) 
    showing delivery time distribution by category
    """
    fig = px.box(
        df_filtered,
        x='category',
        y='delivery_time',
        color='category',
        title='Delivery Time Distribution by Product Category',
        labels={
            'category': 'Product Category',
            'delivery_time': 'Delivery Time (min)'
        },
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    
    fig.update_layout(height=450, showlegend=False)
    
    return fig

# ==================== OPTIONAL VISUALIZATIONS ====================

def create_monthly_trend(df_filtered):
    """Optional: Monthly trend line chart"""
    # If date column exists
    if 'date' in df_filtered.columns or 'delivery_date' in df_filtered.columns:
        date_col = 'date' if 'date' in df_filtered.columns else 'delivery_date'
        df_filtered[date_col] = pd.to_datetime(df_filtered[date_col], errors='coerce')
        monthly = df_filtered.groupby(df_filtered[date_col].dt.to_period('M')).agg({
            'delivery_time': 'mean'
        }).reset_index()
        monthly[date_col] = monthly[date_col].dt.to_timestamp()
        
        fig = px.line(monthly, x=date_col, y='delivery_time',
                     title='Monthly Delivery Time Trend',
                     labels={'delivery_time': 'Avg Delivery Time (min)'})
        fig.update_layout(height=350)
        return fig
    return None

def create_time_distribution(df_filtered):
    """Optional: Delivery time distribution histogram"""
    fig = px.histogram(
        df_filtered,
        x='delivery_time',
        nbins=30,
        title='Distribution of Delivery Times',
        labels={'delivery_time': 'Delivery Time (min)', 'count': 'Frequency'},
        color_discrete_sequence=['steelblue']
    )
    fig.update_layout(height=350)
    return fig

def create_late_delivery_analysis(df_filtered):
    """Optional: % of late deliveries by traffic and weather"""
    late_by_traffic = df_filtered.groupby('traffic')['is_late'].mean() * 100
    late_by_weather = df_filtered.groupby('weather')['is_late'].mean() * 100
    
    fig = make_subplots(rows=1, cols=2, 
                       subplot_titles=('Late Deliveries by Traffic', 
                                     'Late Deliveries by Weather'))
    
    fig.add_trace(go.Bar(x=late_by_traffic.index, y=late_by_traffic.values,
                        marker_color='coral', showlegend=False),
                 row=1, col=1)
    fig.add_trace(go.Bar(x=late_by_weather.index, y=late_by_weather.values,
                        marker_color='lightseagreen', showlegend=False),
                 row=1, col=2)
    
    fig.update_yaxes(title_text="% Late Deliveries", row=1, col=1)
    fig.update_yaxes(title_text="% Late Deliveries", row=1, col=2)
    fig.update_layout(height=350, title_text="Late Delivery Analysis")
    
    return fig

def create_agent_count_by_area(df_filtered):
    """Optional: Agent count per area"""
    agent_count = df_filtered.groupby('area').size().reset_index(name='count')
    agent_count = agent_count.sort_values('count', ascending=False)
    
    fig = px.bar(agent_count, x='area', y='count',
                title='Number of Deliveries by Area',
                labels={'area': 'Area', 'count': 'Number of Deliveries'},
                color='count', color_continuous_scale='Blues')
    fig.update_layout(height=350)
    return fig

# ==================== MAIN APP ====================

def main():
    # Header
    st.title("🚚 Last-Mile Delivery Analytics Dashboard")
    st.markdown("**LogiSight Analytics Pvt. Ltd.** | FA-2 Project by Jwal Patel")
    st.markdown("---")
    
    # Load data
    with st.spinner("Loading and cleaning data..."):
        df, original_shape, cleaned_shape, late_threshold = load_and_clean_data(
            'data/Last mile Delivery Data.xlsx'
        )
    
    # ==================== SIDEBAR FILTERS ====================
    st.sidebar.header("📊 Dashboard Filters")
    st.sidebar.markdown("Use these filters to explore delivery insights")
    
    # Weather filter
    weather_options = ['All'] + sorted(df['weather'].unique().tolist())
    selected_weather = st.sidebar.multiselect(
        "Weather Condition",
        options=weather_options[1:],
        default=weather_options[1:]
    )
    
    # Traffic filter
    traffic_options = ['All'] + sorted(df['traffic'].unique().tolist())
    selected_traffic = st.sidebar.multiselect(
        "Traffic Level",
        options=traffic_options[1:],
        default=traffic_options[1:]
    )
    
    # Vehicle filter
    vehicle_options = ['All'] + sorted(df['vehicle'].unique().tolist())
    selected_vehicle = st.sidebar.multiselect(
        "Vehicle Type",
        options=vehicle_options[1:],
        default=vehicle_options[1:]
    )
    
    # Area filter
    area_options = ['All'] + sorted(df['area'].unique().tolist())
    selected_area = st.sidebar.multiselect(
        "Delivery Area",
        options=area_options[1:],
        default=area_options[1:]
    )
    
    # Category filter
    category_options = ['All'] + sorted(df['category'].unique().tolist())
    selected_category = st.sidebar.multiselect(
        "Product Category",
        options=category_options[1:],
        default=category_options[1:]
    )
    
    st.sidebar.markdown("---")
    
    # Apply filters
    df_filtered = df.copy()
    
    if selected_weather:
        df_filtered = df_filtered[df_filtered['weather'].isin(selected_weather)]
    if selected_traffic:
        df_filtered = df_filtered[df_filtered['traffic'].isin(selected_traffic)]
    if selected_vehicle:
        df_filtered = df_filtered[df_filtered['vehicle'].isin(selected_vehicle)]
    if selected_area:
        df_filtered = df_filtered[df_filtered['area'].isin(selected_area)]
    if selected_category:
        df_filtered = df_filtered[df_filtered['category'].isin(selected_category)]
    
    # ==================== KEY METRICS ====================
    st.header("📈 Key Performance Indicators")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_time = df_filtered['delivery_time'].mean()
        st.metric(
            "Average Delivery Time",
            f"{avg_time:.1f} min",
            delta=f"{avg_time - df['delivery_time'].mean():.1f} vs overall"
        )
    
    with col2:
        late_pct = (df_filtered['is_late'].mean() * 100)
        st.metric(
            "Late Deliveries",
            f"{late_pct:.1f}%",
            delta=f"{late_pct - (df['is_late'].mean() * 100):.1f}% vs overall",
            delta_color="inverse"
        )
    
    with col3:
        total_deliveries = len(df_filtered)
        st.metric(
            "Total Deliveries",
            f"{total_deliveries:,}",
            delta=f"{total_deliveries - len(df):,} vs overall"
        )
    
    with col4:
        avg_rating = df_filtered['agent_rating'].mean()
        st.metric(
            "Avg Agent Rating",
            f"{avg_rating:.2f}",
            delta=f"{avg_rating - df['agent_rating'].mean():.2f} vs overall"
        )
    
    st.info(f"📌 Late delivery threshold: {late_threshold:.1f} minutes (mean + 1 std dev)")
    st.markdown("---")
    
    # ==================== COMPULSORY VISUALIZATIONS ====================
    
    st.header("🎯 Compulsory Analysis")
    
    # 1. Delay Analyzer
    st.subheader("1️⃣ Delay Analyzer: Impact of Weather & Traffic")
    st.plotly_chart(create_delay_analyzer(df_filtered), use_container_width=True)
    st.caption("📊 This chart helps managers identify which weather and traffic conditions lead to longer delivery times and higher delay rates.")
    
    st.markdown("---")
    
    # 2. Vehicle Comparison
    st.subheader("2️⃣ Vehicle Performance Comparison")
    st.plotly_chart(create_vehicle_comparison(df_filtered), use_container_width=True)
    st.caption("🚗 Compare vehicle types to identify the fastest and most reliable fleet for efficient delivery planning.")
    
    st.markdown("---")
    
    # 3. Agent Performance Scatter (WITH TRENDLINE)
    st.subheader("3️⃣ Agent Insights")
    st.plotly_chart(create_agent_performance_scatter(df_filtered), use_container_width=True)
    st.caption("👤 Analyze the relationship between agent ratings, age groups, and delivery performance for workforce optimization.")
    
    st.markdown("---")
    
    # 4. Area Heatmap
    st.subheader("4️⃣ Geographic Performance Heatmap")
    st.plotly_chart(create_area_heatmap(df_filtered), use_container_width=True)
    st.caption("🗺️ Identify geographic hotspots where delays are common, enabling targeted operational improvements.")
    
    st.markdown("---")
    
    # 5. Category Boxplot
    st.subheader("5️⃣ Product Category Distribution")
    st.plotly_chart(create_category_boxplot(df_filtered), use_container_width=True)
    st.caption("📦 Understand which product categories consistently face longer delivery times for better resource allocation.")
    
    st.markdown("---")
    
    # ==================== OPTIONAL VISUALIZATIONS ====================
    
    with st.expander("🔍 Additional Insights (Optional Visuals)", expanded=False):
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(create_time_distribution(df_filtered), use_container_width=True)
        
        with col2:
            st.plotly_chart(create_late_delivery_analysis(df_filtered), use_container_width=True)
        
        st.plotly_chart(create_agent_count_by_area(df_filtered), use_container_width=True)
    
    # ==================== EXPORT FILTERED SUMMARIES ====================
    
    st.markdown("---")
    st.subheader("📤 Export Filtered Summaries")
    
    # Prepare aggregated data for export
    export_data = {
        'by_traffic': df_filtered.groupby('traffic').agg({
            'delivery_time': 'mean',
            'is_late': lambda x: (x.mean() * 100)
        }).reset_index().rename(columns={'delivery_time': 'avg_time', 'is_late': 'late_pct'}),
        
        'by_weather': df_filtered.groupby('weather').agg({
            'delivery_time': 'mean',
            'is_late': lambda x: (x.mean() * 100)
        }).reset_index().rename(columns={'delivery_time': 'avg_time', 'is_late': 'late_pct'}),
        
        'by_vehicle': df_filtered.groupby('vehicle').agg({
            'delivery_time': 'mean',
            'is_late': lambda x: (x.mean() * 100)
        }).reset_index().rename(columns={'delivery_time': 'avg_time', 'is_late': 'late_pct'}),
        
        'by_area': df_filtered.groupby('area').agg({
            'delivery_time': 'mean',
            'is_late': lambda x: (x.mean() * 100)
        }).reset_index().rename(columns={'delivery_time': 'avg_time', 'is_late': 'late_pct'}),
        
        'by_category': df_filtered.groupby('category').agg({
            'delivery_time': 'mean',
            'is_late': lambda x: (x.mean() * 100)
        }).reset_index().rename(columns={'delivery_time': 'avg_time', 'is_late': 'late_pct'})
    }
    
    # Combine all aggregates
    all_df = pd.concat(export_data, names=['group']).reset_index()
    
    # Download button
    csv_bytes = all_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download CSV snapshot",
        data=csv_bytes,
        file_name="filtered_delivery_summaries.csv",
        mime="text/csv"
    )
    
    st.caption("💡 Download aggregated metrics for all filtered dimensions (Traffic, Weather, Vehicle, Area, Category).")
    
    # ==================== DATA QUALITY INFO ====================
    
    with st.expander("ℹ️ Data Quality Report"):
        st.write("**Original Dataset:**", f"{original_shape[0]} rows × {original_shape[1]} columns")
        st.write("**After Cleaning:**", f"{cleaned_shape[0]} rows × {cleaned_shape[1]} columns")
        st.write("**Rows Removed:**", original_shape[0] - cleaned_shape[0])
        
        st.write("\n**Summary Statistics:**")
        st.dataframe(df_filtered.describe())
        
        st.write("\n**Categorical Value Counts:**")
        col1, col2 = st.columns(2)
        with col1:
            st.write("Weather:", df_filtered['weather'].value_counts().to_dict())
            st.write("Traffic:", df_filtered['traffic'].value_counts().to_dict())
            st.write("Vehicle:", df_filtered['vehicle'].value_counts().to_dict())
        with col2:
            st.write("Area:", df_filtered['area'].value_counts().to_dict())
            st.write("Category:", df_filtered['category'].value_counts().to_dict())
    
    # Footer
    st.markdown("---")
    st.caption("**Data logic:** Load → Clean/Standardize → Derive Delay_Flag & Age_Bin → Aggregate → Apply Filters → Update KPIs & Visuals → Export.")
    st.markdown("""
    <div style='text-align: center; color: gray; padding: 20px;'>
        <p><strong>Last-Mile Delivery Analytics Dashboard</strong></p>
        <p>FA-2 Project | Mathematics for AI-II | CRS: Artificial Intelligence</p>
        <p>Developed by: Jwal Patel | LogiSight Analytics Pvt. Ltd.</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
