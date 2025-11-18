import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import pyodbc
import matplotlib.pyplot as plt

def main():
    st.title("📚 Books Dashboard")
    
    # Initialize session state
    if 'df' not in st.session_state:
        st.session_state.df = None
    
    # Sidebar for actions
    st.sidebar.header("Actions")
    
    # Option 1: Load from CSV
    if st.sidebar.button("Load from CSV"):
        try:
            st.session_state.df = pd.read_csv("books_data.csv")
            st.sidebar.success("Data loaded from CSV!")
        except Exception as e:
            st.sidebar.error(f"Error loading CSV: {e}")
    
    # Option 2: Scrape new data
    if st.sidebar.button("Scrape New Data"):
        with st.spinner("Scraping book data from website..."):
            try:
                data = scrape_books_data()
                st.session_state.df = pd.DataFrame(data)
                st.session_state.df = clean_data(st.session_state.df)
                st.session_state.df.to_csv("books_data.csv", index=False, encoding="utf-8-sig")
                st.sidebar.success("New data scraped and saved!")
            except Exception as e:
                st.sidebar.error(f"Error scraping data: {e}")
    
    # Option 3: Load from database
    if st.sidebar.button("Load from Database"):
        try:
            conn = connect_database()
            if conn:
                st.session_state.df = pd.read_sql("SELECT * FROM BooksTable", conn)
                conn.close()
                st.sidebar.success("Data loaded from database!")
        except Exception as e:
            st.sidebar.error(f"Error loading from database: {e}")
    
    # Get the dataframe
    df = st.session_state.df
    
    if df is None or df.empty:
        st.warning("No data loaded. Please click one of the buttons in the sidebar to load data.")
        return
    
    # DEBUG: Show what columns we have
    st.sidebar.subheader("Debug Info")
    st.sidebar.write("Columns found:", list(df.columns))
    st.sidebar.write("Data shape:", df.shape)
    
    # Display raw data
    st.subheader("📖 All Books Data")
    st.dataframe(df)
    
    # Auto-detect columns
    price_col = detect_column(df, ['price', 'Price', 'price_color'])
    availability_col = detect_column(df, ['availability', 'Availability', 'stock', 'instock'])
    title_col = detect_column(df, ['Title', 'title', 'Book_Name', 'Book_Name', 'name'])
    
    st.write(f"**Detected columns:** Title: `{title_col}`, Price: `{price_col}`, Availability: `{availability_col}`")
    
    # Filter by Price
    if price_col:
        st.subheader("💰 Filter by Price")
        try:
            # Ensure price is numeric
            df[price_col] = pd.to_numeric(df[price_col], errors='coerce')
            df_clean = df.dropna(subset=[price_col])
            
            min_price = int(df_clean[price_col].min())
            max_price = int(df_clean[price_col].max())
            default_price = min(max_price, 50)
            
            selected_price = st.slider(
                "Select maximum price:",
                min_value=min_price,
                max_value=max_price,
                value=default_price
            )
            
            filtered_df = df_clean[df_clean[price_col] <= selected_price]
            st.write(f"**Showing {len(filtered_df)} books priced under {selected_price}**")
            st.dataframe(filtered_df)
            
        except Exception as e:
            st.error(f"Error with price filtering: {e}")
            filtered_df = df
    else:
        st.warning("⚠️ Price column not found in the data")
        filtered_df = df
    
    # Books In Stock
    if availability_col:
        st.subheader("✅ Books In Stock")
        try:
            # Convert to string and lowercase for comparison
            in_stock_mask = df[availability_col].astype(str).str.lower().str.contains('in stock', na=False)
            in_stock_df = df[in_stock_mask]
            st.write(f"**Found {len(in_stock_df)} books in stock**")
            st.dataframe(in_stock_df)
        except Exception as e:
            st.error(f"Error filtering in-stock books: {e}")
    else:
        st.warning("⚠️ Availability column not found")
    
    # Search Books
    if title_col:
        st.subheader("🔍 Search Books")
        search_term = st.text_input("Enter book title to search:")
        if search_term:
            try:
                search_results = df[df[title_col].astype(str).str.contains(search_term, case=False, na=False)]
                st.write(f"**Found {len(search_results)} matching books**")
                st.dataframe(search_results)
            except Exception as e:
                st.error(f"Error searching books: {e}")
    
    # Visualizations
    if price_col:
        st.subheader("📊 Price Distribution")
        try:
            st.bar_chart(df[price_col])
        except Exception as e:
            st.error(f"Error creating chart: {e}")
        
        # Additional plots
        if st.checkbox("Show advanced charts"):
            col1, col2 = st.columns(2)
            
            with col1:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.hist(df[price_col].dropna(), bins=20, color='lightblue', edgecolor='black')
                ax.set_title('Price Distribution')
                ax.set_xlabel('Price')
                ax.set_ylabel('Count')
                st.pyplot(fig)
            
            with col2:
                fig, ax = plt.subplots(figsize=(8, 6))
                ax.boxplot(df[price_col].dropna())
                ax.set_title('Price Box Plot')
                ax.set_ylabel('Price')
                st.pyplot(fig)
    
    # Download
    st.subheader("📥 Download Data")
    st.download_button(
        label="Download Filtered Data as CSV",
        data=filtered_df.to_csv(index=False).encode('utf-8'),
        file_name='filtered_books.csv',
        mime='text/csv'
    )

def detect_column(df, possible_names):
    """Detect which column name exists in the dataframe"""
    for name in possible_names:
        if name in df.columns:
            return name
    # Try partial matching
    for col in df.columns:
        for name in possible_names:
            if name.lower() in col.lower():
                return col
    return None

def scrape_books_data():
    """Scrape book data from books.toscrape.com"""
    base_url = 'https://books.toscrape.com/catalogue/page-{}.html'
    data = []
    
    # Just scrape first 5 pages for demo (to make it faster)
    for page in range(1, 6):
        url = base_url.format(page)
        try:
            web = requests.get(url)
            soup = BeautifulSoup(web.text, 'html.parser')
            
            books_list = soup.find('ol', class_='row')
            if books_list:
                books = books_list.find_all('article', class_='product_pod')
                
                for book in books:
                    title = book.h3.a['title']
                    price = book.find('p', class_='price_color').text
                    availability = book.find('p', class_='instock availability').text.strip()
                    
                    data.append({
                        'Book_Name': title,
                        'price': price,
                        'availability': availability
                    })
        except Exception as e:
            st.error(f"Error scraping page {page}: {e}")
    
    return data

def clean_data(df):
    """Clean and process the book data"""
    try:
        df['price'] = df['price'].str.replace('Â£', '').astype(float)
        df['price'] = df['price'].astype(int)
    except Exception as e:
        st.error(f"Error cleaning data: {e}")
    return df

def connect_database():
    """Connect to SQL Server database"""
    try:
        conn = pyodbc.connect(
            "Driver={ODBC Driver 18 for SQL Server};"
            "Server=DESKTOP-RLMEU2F;"
            "Database=BooksDB;"
            "Trusted_Connection=yes;"
            "Encrypt=no;"
        )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

if __name__ == "__main__":
    main()