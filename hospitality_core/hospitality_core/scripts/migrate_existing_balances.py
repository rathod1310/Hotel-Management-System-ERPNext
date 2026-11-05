#!/usr/bin/env python3
"""
Script to migrate existing guest credit balances to the Guest Balance Ledger.

This script finds all closed folios with credit balances (outstanding_balance < 0)
and creates Guest Balance Ledger entries for them if they don't already exist.

Usage:
    bench --site [site-name] execute hospitality_core.hospitality_core.scripts.migrate_existing_balances.run
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

def run():
    """
    Main function to migrate existing guest balances.
    """
    frappe.init(site=frappe.local.site)
    frappe.connect()
    
    print("\n" + "="*60)
    print("Guest Balance Ledger Migration")
    print("="*60 + "\n")
    
    # Find all closed folios with credit balances
    folios = frappe.db.sql("""
        SELECT 
            name, guest, outstanding_balance, close_date
        FROM 
            `tabGuest Folio`
        WHERE 
            status = 'Closed'
            AND outstanding_balance < -0.01
            AND guest IS NOT NULL
            AND guest != ''
        ORDER BY 
            close_date DESC
    """, as_dict=True)
    
    if not folios:
        print("✓ No closed folios with credit balances found.")
        print("  Nothing to migrate.\n")
        return
    
    print(f"Found {len(folios)} closed folio(s) with credit balances.\n")
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    for folio in folios:
        try:
            # Check if ledger entry already exists
            exists = frappe.db.exists("Guest Balance Ledger", {"folio": folio.name})
            
            if exists:
                print(f"⊘ Skipping {folio.name} - Already has ledger entry")
                skipped_count += 1
                continue
            
            credit_amount = abs(flt(folio.outstanding_balance))
            
            # Create Guest Balance Ledger entry
            ledger_entry = frappe.new_doc("Guest Balance Ledger")
            ledger_entry.guest = folio.guest
            ledger_entry.folio = folio.name
            ledger_entry.amount = credit_amount
            ledger_entry.status = "Available"
            ledger_entry.date = folio.close_date or nowdate()
            ledger_entry.insert(ignore_permissions=True)
            
            guest_name = frappe.db.get_value("Guest", folio.guest, "full_name")
            print(f"✓ Created ledger entry for {folio.name}")
            print(f"  Guest: {guest_name} ({folio.guest})")
            print(f"  Amount: {frappe.format(credit_amount, {'fieldtype': 'Currency'})}")
            print(f"  Date: {ledger_entry.date}\n")
            
            created_count += 1
            
        except Exception as e:
            error_count += 1
            print(f"✗ Error processing {folio.name}: {str(e)}\n")
            frappe.log_error(
                message=f"Failed to create Guest Balance Ledger for {folio.name}: {str(e)}",
                title="Guest Balance Migration Error"
            )
    
    # Commit the changes
    frappe.db.commit()
    
    # Summary
    print("="*60)
    print("Migration Summary")
    print("="*60)
    print(f"Total folios processed: {len(folios)}")
    print(f"✓ Ledger entries created: {created_count}")
    print(f"⊘ Already had entries (skipped): {skipped_count}")
    print(f"✗ Errors: {error_count}")
    print("="*60 + "\n")
    
    if created_count > 0:
        print(f"Successfully migrated {created_count} guest balance(s)!")
    
    if error_count > 0:
        print(f"\n⚠ {error_count} error(s) occurred. Check Error Log for details.")

if __name__ == "__main__":
    run()
