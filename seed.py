"""
BloodBeacon Seed Script
Populates the database with test data: donors, hospitals, and NBTC rules.
Run with: python seed.py (requires Supabase credentials in .env)
"""

from datetime import datetime, timedelta
import db

# Test data: ~36 seed donors across all 8 blood groups in Tiruchirappalli and Chennai
SEED_DONORS = [
    # Tiruchirappalli - O+
    {"name": "SEED_Raj Kumar", "blood_group": "O+", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543210", "gender": "Male", "date_of_birth": "1990-05-15", "weight_kg": 70},
    {"name": "SEED_Priya Sharma", "blood_group": "O+", "city": "Tiruchirappalli", "area": "Thillai Nagar", 
     "phone": "9876543211", "gender": "Female", "date_of_birth": "1992-08-20", "weight_kg": 60},
    {"name": "SEED_Arjun Singh", "blood_group": "O+", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543212", "gender": "Male", "date_of_birth": "1988-03-10", "weight_kg": 75},
    
    # Tiruchirappalli - O-
    {"name": "SEED_Deepak Reddy", "blood_group": "O-", "city": "Tiruchirappalli", "area": "Srirangam", 
     "phone": "9876543213", "gender": "Male", "date_of_birth": "1991-07-22", "weight_kg": 72},
    {"name": "SEED_Anjali Gupta", "blood_group": "O-", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543214", "gender": "Female", "date_of_birth": "1993-12-05", "weight_kg": 58},
    
    # Tiruchirappalli - A+
    {"name": "SEED_Vikram Patel", "blood_group": "A+", "city": "Tiruchirappalli", "area": "Thillai Nagar", 
     "phone": "9876543215", "gender": "Male", "date_of_birth": "1989-01-30", "weight_kg": 73},
    {"name": "SEED_Neha Verma", "blood_group": "A+", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543216", "gender": "Female", "date_of_birth": "1994-06-14", "weight_kg": 62},
    {"name": "SEED_Rohan Yadav", "blood_group": "A+", "city": "Tiruchirappalli", "area": "Srirangam", 
     "phone": "9876543217", "gender": "Male", "date_of_birth": "1987-09-18", "weight_kg": 76},
    
    # Tiruchirappalli - A-
    {"name": "SEED_Suresh Iyer", "blood_group": "A-", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543218", "gender": "Male", "date_of_birth": "1992-04-25", "weight_kg": 68},
    
    # Tiruchirappalli - B+
    {"name": "SEED_Akshay Desai", "blood_group": "B+", "city": "Tiruchirappalli", "area": "Thillai Nagar", 
     "phone": "9876543219", "gender": "Male", "date_of_birth": "1990-11-03", "weight_kg": 74},
    {"name": "SEED_Divya Nair", "blood_group": "B+", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543220", "gender": "Female", "date_of_birth": "1993-02-17", "weight_kg": 65},
    {"name": "SEED_Sanjay Kulkarni", "blood_group": "B+", "city": "Tiruchirappalli", "area": "Srirangam", 
     "phone": "9876543221", "gender": "Male", "date_of_birth": "1991-10-08", "weight_kg": 79},
    
    # Tiruchirappalli - B-
    {"name": "SEED_Isha Chopra", "blood_group": "B-", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543222", "gender": "Female", "date_of_birth": "1994-08-12", "weight_kg": 59},
    
    # Tiruchirappalli - AB+
    {"name": "SEED_Varun Bhat", "blood_group": "AB+", "city": "Tiruchirappalli", "area": "Thillai Nagar", 
     "phone": "9876543223", "gender": "Male", "date_of_birth": "1989-05-20", "weight_kg": 71},
    
    # Tiruchirappalli - AB-
    {"name": "SEED_Shreya Menon", "blood_group": "AB-", "city": "Tiruchirappalli", "area": "Cantonment", 
     "phone": "9876543224", "gender": "Female", "date_of_birth": "1995-03-09", "weight_kg": 61},
    
    # Chennai - O+
    {"name": "SEED_Anil Kumar", "blood_group": "O+", "city": "Chennai", "area": "Mylapore", 
     "phone": "9876543225", "gender": "Male", "date_of_birth": "1988-07-16", "weight_kg": 77},
    {"name": "SEED_Kavya Iyer", "blood_group": "O+", "city": "Chennai", "area": "Nungambakkam", 
     "phone": "9876543226", "gender": "Female", "date_of_birth": "1992-09-21", "weight_kg": 63},
    {"name": "SEED_Nikhil Sharma", "blood_group": "O+", "city": "Chennai", "area": "Velachery", 
     "phone": "9876543227", "gender": "Male", "date_of_birth": "1990-01-11", "weight_kg": 75},
    
    # Chennai - O-
    {"name": "SEED_Ravi Sundar", "blood_group": "O-", "city": "Chennai", "area": "Mylapore", 
     "phone": "9876543228", "gender": "Male", "date_of_birth": "1991-06-28", "weight_kg": 70},
    {"name": "SEED_Pooja Das", "blood_group": "O-", "city": "Chennai", "area": "Adyar", 
     "phone": "9876543229", "gender": "Female", "date_of_birth": "1993-11-14", "weight_kg": 60},
    
    # Chennai - A+
    {"name": "SEED_Harish Reddy", "blood_group": "A+", "city": "Chennai", "area": "Velachery", 
     "phone": "9876543230", "gender": "Male", "date_of_birth": "1989-04-09", "weight_kg": 72},
    {"name": "SEED_Meera Roy", "blood_group": "A+", "city": "Chennai", "area": "Nungambakkam", 
     "phone": "9876543231", "gender": "Female", "date_of_birth": "1994-10-19", "weight_kg": 64},
    {"name": "SEED_Vikrant Singh", "blood_group": "A+", "city": "Chennai", "area": "Mylapore", 
     "phone": "9876543232", "gender": "Male", "date_of_birth": "1987-12-02", "weight_kg": 78},
    
    # Chennai - A-
    {"name": "SEED_Amrita Koul", "blood_group": "A-", "city": "Chennai", "area": "Adyar", 
     "phone": "9876543233", "gender": "Female", "date_of_birth": "1993-05-11", "weight_kg": 61},
    
    # Chennai - B+
    {"name": "SEED_Mohit Jain", "blood_group": "B+", "city": "Chennai", "area": "Velachery", 
     "phone": "9876543234", "gender": "Male", "date_of_birth": "1990-08-27", "weight_kg": 74},
    {"name": "SEED_Anjum Khan", "blood_group": "B+", "city": "Chennai", "area": "Nungambakkam", 
     "phone": "9876543235", "gender": "Female", "date_of_birth": "1992-02-06", "weight_kg": 62},
    {"name": "SEED_Arjun Nair", "blood_group": "B+", "city": "Chennai", "area": "Mylapore", 
     "phone": "9876543236", "gender": "Male", "date_of_birth": "1991-09-13", "weight_kg": 80},
    
    # Chennai - B-
    {"name": "SEED_Simran Walia", "blood_group": "B-", "city": "Chennai", "area": "Adyar", 
     "phone": "9876543237", "gender": "Female", "date_of_birth": "1994-07-23", "weight_kg": 58},
    
    # Chennai - AB+
    {"name": "SEED_Ashok Mishra", "blood_group": "AB+", "city": "Chennai", "area": "Velachery", 
     "phone": "9876543238", "gender": "Male", "date_of_birth": "1989-03-15", "weight_kg": 69},
    
    # Chennai - AB-
    {"name": "SEED_Radha Krishnan", "blood_group": "AB-", "city": "Chennai", "area": "Nungambakkam", 
     "phone": "9876543239", "gender": "Female", "date_of_birth": "1995-01-08", "weight_kg": 63},
]

# Add two more for each blood group to reach ~36
ADDITIONAL_DONORS = [
    {"name": "SEED_Sandeep Verma", "blood_group": "O+", "city": "Tiruchirappalli", "area": "Srirangam", 
     "phone": "9876543240", "gender": "Male", "date_of_birth": "1991-02-10", "weight_kg": 72},
    {"name": "SEED_Preeti Saxena", "blood_group": "A+", "city": "Chennai", "area": "Adyar", 
     "phone": "9876543241", "gender": "Female", "date_of_birth": "1993-07-17", "weight_kg": 65},
    {"name": "SEED_Rahul Tiwari", "blood_group": "B+", "city": "Tiruchirappalli", "area": "Thillai Nagar", 
     "phone": "9876543242", "gender": "Male", "date_of_birth": "1990-12-19", "weight_kg": 76},
]

# NBTC Rules (from context)
SEED_RULES = [
    {"key": "age_min", "value": "18", "description": "Minimum age for donation (years)"},
    {"key": "age_max", "value": "65", "description": "Maximum age for donation (years)"},
    {"key": "weight_min_kg", "value": "45", "description": "Minimum weight for donation (kg)"},
    {"key": "hemoglobin_min", "value": "12.5", "description": "Minimum hemoglobin level (g/dL)"},
    {"key": "donation_gap_men_days", "value": "90", "description": "Days between donations for men"},
    {"key": "donation_gap_women_days", "value": "120", "description": "Days between donations for women"},
    {"key": "tattoo_deferral_days", "value": "365", "description": "Deferral period for tattoo/piercing (days)"},
    {"key": "TODO_verify_major_surgery", "value": "varies", "description": "TODO: Specify deferral for major surgery"},
    {"key": "TODO_verify_pregnancy", "value": "varies", "description": "TODO: Pregnancy deferral rules"},
    {"key": "TODO_verify_recent_fever", "value": "varies", "description": "TODO: Fever deferral rules"},
    {"key": "TODO_verify_antibiotics", "value": "varies", "description": "TODO: Antibiotics deferral rules"},
]

def seed_database():
    """Populate the database with seed data."""
    if not db.is_db_configured():
        print("❌ Error: Supabase credentials not configured in .env")
        print("   Copy .env.example to .env and fill in your Supabase credentials.")
        return False

    try:
        print("🌱 Starting seed...")
        
        # Seed donors
        all_donors = SEED_DONORS + ADDITIONAL_DONORS
        print(f"\n📋 Seeding {len(all_donors)} donors...")
        
        inserted_donors = []
        for donor_data in all_donors:
            try:
                donor = db.insert_donor(**donor_data)
                if donor:
                    inserted_donors.append(donor)
                    print(f"  ✓ {donor_data['name']} ({donor_data['blood_group']}) - {donor_data['city']}")
            except Exception as e:
                print(f"  ⚠️  {donor_data['name']}: {str(e)}")
        
        print(f"\n✅ Seeded {len(inserted_donors)}/{len(all_donors)} donors")
        
        # Seed rules
        print(f"\n📋 Seeding {len(SEED_RULES)} NBTC rules...")
        inserted_rules = 0
        for rule_data in SEED_RULES:
            try:
                db.insert_rule(**rule_data)
                inserted_rules += 1
                print(f"  ✓ {rule_data['key']}")
            except Exception as e:
                print(f"  ⚠️  {rule_data['key']}: {str(e)}")
        
        print(f"\n✅ Seeded {inserted_rules}/{len(SEED_RULES)} rules")
        
        # Seed donations (some donors have past donations to vary last-donation dates)
        print(f"\n📋 Seeding donations (varied last-donation dates)...")
        donations_added = 0
        
        # Add donations with varied dates for first 12 donors
        for i, donor in enumerate(inserted_donors[:12]):
            try:
                # Vary donation dates: some within 30 days, some 60, 90, 100+ days ago
                days_ago = [15, 25, 60, 75, 90, 100, 110, 120, 30, 50, 80, 95][i]
                donation_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
                
                db.insert_donation(
                    donor_id=donor["id"],
                    donated_on=donation_date,
                    units=1.0,
                    source="self_report"
                )
                donations_added += 1
                print(f"  ✓ {donor['name']} - {days_ago} days ago")
            except Exception as e:
                print(f"  ⚠️  Donation for {donor['name']}: {str(e)}")
        
        print(f"\n✅ Seeded {donations_added} donations")
        
        print("\n" + "="*50)
        print("✅ Seed complete!")
        print("="*50)
        return True
        
    except Exception as e:
        print(f"\n❌ Error during seed: {str(e)}")
        return False

if __name__ == "__main__":
    seed_database()
