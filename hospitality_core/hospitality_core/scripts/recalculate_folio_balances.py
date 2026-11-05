
import frappe
from hospitality_core.hospitality_core.api.folio import sync_folio_balance

def run():
    """
    Recalculates balances for all Guest Folios to separate discounts from payments.
    """
    print("\n" + "="*60)
    print("Guest Folio Discount Separation Migration")
    print("="*60 + "\n")
    
    folios = frappe.get_all("Guest Folio", fields=["name"])
    
    total = len(folios)
    print(f"Found {total} folios to process.\n")
    
    count = 0
    errors = 0
    
    for f in folios:
        try:
            doc = frappe.get_doc("Guest Folio", f.name)
            sync_folio_balance(doc)
            count += 1
            if count % 10 == 0:
                print(f"✓ Processed {count}/{total} folios...")
        except Exception as e:
            errors += 1
            print(f"✗ Error processing {f.name}: {str(e)}")
            
    frappe.db.commit()
    print("\n" + "="*60)
    print("Migration Complete")
    print("="*60)
    print(f"Total folios: {total}")
    print(f"✓ Updated: {count}")
    print(f"✗ Errors: {errors}")
    print("="*60 + "\n")

if __name__ == "__main__":
    run()
