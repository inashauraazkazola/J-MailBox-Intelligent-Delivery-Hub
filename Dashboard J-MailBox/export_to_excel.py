import sqlite3
import pandas as pd
from datetime import datetime
import os

def export_database_to_excel(db_path='jmailbox.db', output_file='jmailbox_data_export.xlsx'):
    """
    Export all tables from SQLite database to Excel with multiple sheets
    """
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Get list of tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    if not tables:
        print("❌ No tables found in database!")
        return
    
    # Create Excel writer
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_filename = f'jmailbox_export_{timestamp}.xlsx'
    
    with pd.ExcelWriter(output_filename, engine='openpyxl') as writer:
        print(f"📊 Exporting data from {db_path}...")
        
        for table_tuple in tables:
            table_name = table_tuple[0]
            
            try:
                # Read table into DataFrame
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql_query(query, conn)
                
                if not df.empty:
                    # Write to Excel sheet
                    df.to_excel(writer, sheet_name=table_name, index=False)
                    print(f"✅ Exported table: {table_name} ({len(df)} rows)")
                else:
                    print(f"⚠️  Table {table_name} is empty")
                    
            except Exception as e:
                print(f"❌ Error exporting table {table_name}: {e}")
        
        # Create summary sheet
        create_summary_sheet(writer, tables, conn)
    
    conn.close()
    
    print(f"\n🎉 Export completed successfully!")
    print(f"📁 File saved as: {output_filename}")
    print(f"📏 File size: {os.path.getsize(output_filename) / 1024:.2f} KB")
    
    return output_filename

def create_summary_sheet(writer, tables, conn):
    """
    Create a summary sheet with table information
    """
    summary_data = []
    
    for table_tuple in tables:
        table_name = table_tuple[0]
        
        try:
            # Get row count
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # Get column information
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            columns = [col[1] for col in columns_info]
            column_count = len(columns)
            
            # Get data types
            data_types = [col[2] for col in columns_info]
            
            summary_data.append({
                'Table Name': table_name,
                'Rows': row_count,
                'Columns': column_count,
                'Column Names': ', '.join(columns),
                'Main Data Types': ', '.join(set(data_types))[:50] + '...' if len(set(data_types)) > 3 else ', '.join(set(data_types))
            })
            
        except Exception as e:
            summary_data.append({
                'Table Name': table_name,
                'Rows': 'Error',
                'Columns': 'Error',
                'Column Names': f'Error: {str(e)}',
                'Main Data Types': 'Error'
            })
    
    # Create DataFrame and write to Excel
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='SUMMARY', index=False)
    
    # Add timestamp and database info
    ws = writer.sheets['SUMMARY']
    ws['F1'] = 'J-MailBox Database Export'
    ws['F2'] = f'Export Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
    ws['F3'] = 'Database: jmailbox.db'
    ws['F4'] = f'Total Tables: {len(tables)}'
    
    print(f"✅ Created summary sheet")

def export_detailed_report():
    """
    Create a more detailed report with user analysis
    """
    conn = sqlite3.connect('jmailbox.db')
    
    try:
        # Read all tables
        users_df = pd.read_sql_query("SELECT * FROM users", conn)
        master_df = pd.read_sql_query("SELECT * FROM master_data", conn)
        packages_df = pd.read_sql_query("SELECT * FROM packages", conn)
        security_df = pd.read_sql_query("SELECT * FROM security_logs", conn)
        settings_df = pd.read_sql_query("SELECT * FROM settings", conn)
        activity_df = pd.read_sql_query("SELECT * FROM activity_logs", conn)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f'jmailbox_detailed_report_{timestamp}.xlsx'
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            
            # 1. USERS sheet with analysis
            users_df.to_excel(writer, sheet_name='USERS', index=False)
            
            # 2. MASTER DATA sheet
            master_df.to_excel(writer, sheet_name='MASTER_DATA', index=False)
            
            # 3. PACKAGES sheet with analysis
            packages_df.to_excel(writer, sheet_name='PACKAGES', index=False)
            
            # 4. SECURITY LOGS sheet
            security_df.to_excel(writer, sheet_name='SECURITY_LOGS', index=False)
            
            # 5. SETTINGS sheet
            settings_df.to_excel(writer, sheet_name='SETTINGS', index=False)
            
            # 6. ACTIVITY LOGS sheet
            activity_df.to_excel(writer, sheet_name='ACTIVITY_LOGS', index=False)
            
            # 7. ANALYSIS sheet with statistics
            create_analysis_sheet(writer, users_df, master_df, packages_df, security_df, activity_df)
            
            # 8. DATA DICTIONARY sheet
            create_data_dictionary(writer, conn)
        
        conn.close()
        
        print(f"\n📈 Detailed report created: {output_file}")
        return output_file
        
    except Exception as e:
        print(f"❌ Error creating detailed report: {e}")
        conn.close()
        return None

def create_analysis_sheet(writer, users_df, master_df, packages_df, security_df, activity_df):
    """
    Create analysis sheet with statistics
    """
    analysis_data = []
    
    # User Statistics
    if not users_df.empty:
        analysis_data.append({
            'Category': 'Users',
            'Metric': 'Total Users',
            'Value': len(users_df),
            'Details': f'Active: {len(users_df[users_df["is_active"] == 1])}'
        })
        
        analysis_data.append({
            'Category': 'Users',
            'Metric': 'Roles Distribution',
            'Value': users_df['role'].value_counts().to_dict(),
            'Details': ''
        })
    
    # Master Data Statistics
    if not master_df.empty:
        analysis_data.append({
            'Category': 'Master Data',
            'Metric': 'Total Recipients',
            'Value': len(master_df),
            'Details': f'Default: {len(master_df[master_df["is_default"] == 1])}'
        })
    
    # Packages Statistics
    if not packages_df.empty:
        analysis_data.append({
            'Category': 'Packages',
            'Metric': 'Total Packages',
            'Value': len(packages_df),
            'Details': f'Status: {packages_df["status"].value_counts().to_dict()}'
        })
        
        analysis_data.append({
            'Category': 'Packages',
            'Metric': 'Payment Methods',
            'Value': packages_df['metode_pembayaran'].value_counts().to_dict(),
            'Details': ''
        })
        
        # Monthly trend
        if 'created_at' in packages_df.columns:
            packages_df['created_at'] = pd.to_datetime(packages_df['created_at'])
            monthly_count = packages_df['created_at'].dt.to_period('M').value_counts().sort_index()
            analysis_data.append({
                'Category': 'Packages',
                'Metric': 'Monthly Trend',
                'Value': monthly_count.to_dict(),
                'Details': ''
            })
    
    # Security Statistics
    if not security_df.empty:
        analysis_data.append({
            'Category': 'Security',
            'Metric': 'Total Security Logs',
            'Value': len(security_df),
            'Details': f'Status: {security_df["status"].value_counts().to_dict()}'
        })
        
        if 'sensor_value' in security_df.columns:
            analysis_data.append({
                'Category': 'Security',
                'Metric': 'Sensor Value Stats',
                'Value': {
                    'Min': security_df['sensor_value'].min(),
                    'Max': security_df['sensor_value'].max(),
                    'Avg': security_df['sensor_value'].mean()
                },
                'Details': ''
            })
    
    # Activity Statistics
    if not activity_df.empty:
        analysis_data.append({
            'Category': 'Activity',
            'Metric': 'Total Activities',
            'Value': len(activity_df),
            'Details': f'Last Activity: {activity_df["timestamp"].max() if "timestamp" in activity_df.columns else "N/A"}'
        })
        
        analysis_data.append({
            'Category': 'Activity',
            'Metric': 'Top Actions',
            'Value': activity_df['action'].value_counts().head(10).to_dict(),
            'Details': ''
        })
    
    # Convert to DataFrame
    analysis_df = pd.DataFrame(analysis_data)
    analysis_df.to_excel(writer, sheet_name='ANALYSIS', index=False)
    
    print(f"✅ Created analysis sheet with {len(analysis_data)} metrics")

def create_data_dictionary(writer, conn):
    """
    Create data dictionary with column descriptions
    """
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    dict_data = []
    
    for table_tuple in tables:
        table_name = table_tuple[0]
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        for col in columns:
            col_id, col_name, col_type, not_null, default_val, pk = col
            
            # Determine data type description
            if 'INT' in col_type.upper():
                type_desc = 'Integer'
            elif 'TEXT' in col_type.upper():
                type_desc = 'Text/String'
            elif 'REAL' in col_type.upper():
                type_desc = 'Floating Point Number'
            elif 'BOOL' in col_type.upper():
                type_desc = 'Boolean (True/False)'
            elif 'TIMESTAMP' in col_type.upper() or 'DATETIME' in col_type.upper():
                type_desc = 'Date/Time'
            else:
                type_desc = col_type
            
            # Determine constraints
            constraints = []
            if pk:
                constraints.append('Primary Key')
            if not_null:
                constraints.append('Not Null')
            if default_val:
                constraints.append(f'Default: {default_val}')
            
            dict_data.append({
                'Table': table_name,
                'Column Name': col_name,
                'Data Type': type_desc,
                'Constraints': ', '.join(constraints) if constraints else 'None',
                'Description': get_column_description(table_name, col_name)
            })
    
    # Create DataFrame
    dict_df = pd.DataFrame(dict_data)
    dict_df.to_excel(writer, sheet_name='DATA_DICTIONARY', index=False)
    
    print(f"✅ Created data dictionary with {len(dict_data)} columns")

def get_column_description(table_name, column_name):
    """
    Get human-readable description for columns
    """
    descriptions = {
        'users': {
            'id': 'Unique user identifier',
            'username': 'Login username',
            'email': 'User email address',
            'nama_lengkap': 'Full name of user',
            'password_hash': 'Hashed password',
            'role': 'User role (admin/user)',
            'created_at': 'Account creation timestamp',
            'last_login': 'Last login timestamp',
            'is_active': 'Account status (1=active, 0=inactive)'
        },
        'master_data': {
            'id': 'Unique master data identifier',
            'name': 'Recipient full name',
            'address': 'Delivery address',
            'phone': 'Phone number',
            'email': 'Email address',
            'is_default': 'Default recipient flag',
            'created_by': 'User ID who created this',
            'created_at': 'Creation timestamp',
            'updated_at': 'Last update timestamp'
        },
        'packages': {
            'id': 'Unique package identifier',
            'resi': 'Tracking number',
            'courier': 'Delivery service provider',
            'nama_penerima': 'Recipient name',
            'alamat': 'Delivery address',
            'telepon': 'Recipient phone',
            'email': 'Recipient email',
            'metode_pembayaran': 'Payment method (COD/Transfer)',
            'status': 'Package status',
            'tanggal': 'Package date',
            'nominal': 'Amount (for COD)',
            'created_at': 'Creation timestamp',
            'updated_at': 'Last update timestamp',
            'master_data_id': 'Reference to master data',
            'created_by': 'User ID who created this'
        },
        'security_logs': {
            'id': 'Unique log identifier',
            'sensor_value': 'Distance in cm',
            'status': 'Security status',
            'probability': 'Safety probability %',
            'timestamp': 'Log timestamp',
            'created_by': 'User ID'
        },
        'settings': {
            'key': 'Setting name',
            'value': 'Setting value',
            'updated_at': 'Last update timestamp'
        },
        'activity_logs': {
            'id': 'Unique activity identifier',
            'user_id': 'User who performed action',
            'action': 'Action performed',
            'details': 'Action details',
            'ip_address': 'IP address',
            'timestamp': 'Activity timestamp'
        }
    }
    
    return descriptions.get(table_name, {}).get(column_name, 'No description available')

def generate_user_report():
    """
    Generate a comprehensive user report
    """
    conn = sqlite3.connect('jmailbox.db')
    
    try:
        # Get user data with activity stats
        query = """
        SELECT 
            u.id,
            u.username,
            u.email,
            u.nama_lengkap,
            u.role,
            u.created_at,
            u.last_login,
            u.is_active,
            COUNT(DISTINCT p.id) as total_packages,
            COUNT(DISTINCT m.id) as total_master_data,
            COUNT(DISTINCT a.id) as total_activities,
            MAX(a.timestamp) as last_activity
        FROM users u
        LEFT JOIN packages p ON u.id = p.created_by
        LEFT JOIN master_data m ON u.id = m.created_by
        LEFT JOIN activity_logs a ON u.id = a.user_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
        """
        
        user_report = pd.read_sql_query(query, conn)
        
        if not user_report.empty:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'jmailbox_user_report_{timestamp}.xlsx'
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # User report
                user_report.to_excel(writer, sheet_name='USER_REPORT', index=False)
                
                # User summary
                summary_data = {
                    'Metric': [
                        'Total Users',
                        'Active Users',
                        'Admin Users',
                        'Regular Users',
                        'Users with Packages',
                        'Users with Master Data',
                        'Average Packages per User',
                        'Average Master Data per User'
                    ],
                    'Value': [
                        len(user_report),
                        len(user_report[user_report['is_active'] == 1]),
                        len(user_report[user_report['role'] == 'admin']),
                        len(user_report[user_report['role'] == 'user']),
                        len(user_report[user_report['total_packages'] > 0]),
                        len(user_report[user_report['total_master_data'] > 0]),
                        user_report['total_packages'].mean(),
                        user_report['total_master_data'].mean()
                    ]
                }
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='USER_SUMMARY', index=False)
                
                # Recent activities
                activity_query = """
                SELECT 
                    a.timestamp,
                    u.username,
                    u.nama_lengkap,
                    a.action,
                    a.details,
                    a.ip_address
                FROM activity_logs a
                LEFT JOIN users u ON a.user_id = u.id
                ORDER BY a.timestamp DESC
                LIMIT 100
                """
                
                recent_activities = pd.read_sql_query(activity_query, conn)
                recent_activities.to_excel(writer, sheet_name='RECENT_ACTIVITIES', index=False)
            
            conn.close()
            
            print(f"\n👥 User report created: {output_file}")
            print(f"📊 Total users: {len(user_report)}")
            print(f"👑 Admin users: {len(user_report[user_report['role'] == 'admin'])}")
            print(f"📦 Users with packages: {len(user_report[user_report['total_packages'] > 0])}")
            
            return output_file
        else:
            print("❌ No user data found")
            return None
            
    except Exception as e:
        print(f"❌ Error generating user report: {e}")
        conn.close()
        return None

def main():
    """Main function to run export"""
    print("=" * 60)
    print("📊 J-MailBox Database Export Tool")
    print("=" * 60)
    print("\nSelect export option:")
    print("1. Basic Export (All tables to Excel)")
    print("2. Detailed Report (With analysis)")
    print("3. User Report (User statistics)")
    print("4. Export All (All reports)")
    print("5. Exit")
    
    choice = input("\nEnter your choice (1-5): ").strip()
    
    if choice == '1':
        # Basic export
        export_database_to_excel()
        
    elif choice == '2':
        # Detailed report
        export_detailed_report()
        
    elif choice == '3':
        # User report
        generate_user_report()
        
    elif choice == '4':
        # Export all
        print("\n🚀 Exporting all reports...")
        
        # Basic export
        basic_file = export_database_to_excel()
        
        # Detailed report
        detailed_file = export_detailed_report()
        
        # User report
        user_file = generate_user_report()
        
        print("\n" + "=" * 60)
        print("🎉 All exports completed!")
        if basic_file:
            print(f"📁 Basic Export: {basic_file}")
        if detailed_file:
            print(f"📁 Detailed Report: {detailed_file}")
        if user_file:
            print(f"📁 User Report: {user_file}")
        print("=" * 60)
        
    elif choice == '5':
        print("👋 Goodbye!")
        
    else:
        print("❌ Invalid choice!")

if __name__ == "__main__":
    # Check if database exists
    if os.path.exists('jmailbox.db'):
        main()
    else:
        print("❌ Database file 'jmailbox.db' not found!")
        print("💡 Make sure you're running this script in the same directory as your database file.")