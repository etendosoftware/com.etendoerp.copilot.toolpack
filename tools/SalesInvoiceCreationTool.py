"""
Sales Invoice Creation Tool

This tool creates sales invoices in Etendo using the provided invoice data.
It handles business partner detection/creation, address management, and invoice line processing.
"""

import json
from typing import Optional, Type

from copilot.core.tool_input import ToolInput
from copilot.core.tool_wrapper import ToolOutput, ToolWrapper
from copilot.core.utils.etendo_utils import (
    call_etendo,
    get_etendo_host,
    get_etendo_token,
)
from copilot.baseutils.logging_envvar import copilot_debug
from copilot.core.exceptions import ToolException
from tools.schemas.invoice import InvoiceAddress, InvoiceLine, InvoiceSchema

# Constants
SIMSEARCH_ENDPOINT = "/webhooks/SimSearch"


class SalesInvoiceCreationTool(ToolWrapper):
    """
    Tool for creating sales invoices in Etendo.

    This tool:
    1. Detects or creates Business Partner by CIF or name using SimSearch
    2. Creates a billing address for the Business Partner
    3. Searches for products using SimSearch (or uses "Producto Generico")
    4. Creates the sales invoice header
    5. Creates invoice lines with products and prices
    """

    name: str = "SalesInvoiceCreationTool"
    description: str = """
    Creates a sales invoice in Etendo from structured invoice data.
    Handles business partner detection/creation, address management, and invoice line processing.
    Requires invoice data following the InvoiceSchema structure.
    """
    args_schema: Type[ToolInput] = InvoiceSchema

    def run(self, input_params: InvoiceSchema, *args, **kwargs) -> ToolOutput:
        """Execute the sales invoice creation process."""
        # Initialize execution log
        execution_log = []

        try:
            if not input_params:
                raise ToolException("input_params is required")

            # Convert dict to InvoiceSchema instance if needed
            if isinstance(input_params, dict):
                invoice = InvoiceSchema(**input_params)
            else:
                invoice = input_params

            # Get Etendo connection details from context
            etendo_url = get_etendo_host()
            token = get_etendo_token()

            copilot_debug(
                f"Processing invoice: {json.dumps(invoice.model_dump(), indent=2)}"
            )
            execution_log.append("🚀 Started sales invoice creation process")
            execution_log.append(
                f"📄 Invoice for: {invoice.businesspartner or 'Unknown'}"
            )
            execution_log.append(f"📅 Date: {invoice.date or 'Not specified'}")
            execution_log.append(f"📋 Lines to process: {len(invoice.lines)}")

            # Print invoice data for initial implementation
            print("=" * 80)
            print("SALES INVOICE CREATION TOOL - Invoice Data Received")
            print("=" * 80)
            print(f"\nBusiness Partner: {invoice.businesspartner}")
            print(f"CIF: {invoice.cif}")
            print(f"Document No.: {invoice.documentno}")
            print(f"Date: {invoice.date}")

            if invoice.address:
                print("\nAddress:")
                print(f"  Street: {invoice.address.street}")
                print(f"  City: {invoice.address.city}")
                print(f"  Postal Code: {invoice.address.postal_code}")
                print(f"  State: {invoice.address.state}")
                print(f"  Country: {invoice.address.country}")

            print(f"\nInvoice Lines ({len(invoice.lines)}):")
            for idx, line in enumerate(invoice.lines, 1):
                print(f"\n  Line {idx}:")
                print(f"    Product: {line.product}")
                print(f"    Quantity: {line.quantity}")
                print(f"    Unit Price: {line.unit_price}")
                print(f"    Tax Rate: {line.tax_rate}%")
                print(f"    Total: {line.total}")

            print("\n" + "=" * 80)

            # Process business partner - CRITICAL: must succeed
            execution_log.append("\n👤 Processing Business Partner...")
            try:
                bp_id, bp_log = self._process_businesspartner(
                    invoice, etendo_url, token
                )
                execution_log.extend(bp_log)
            except Exception as e:
                execution_log.append(
                    f"\n❌ CRITICAL ERROR: Failed to process Business Partner: {str(e)}"
                )
                copilot_debug(f"Critical error processing BP: {str(e)}")
                return {
                    "status": "error",
                    "error": f"Failed to process Business Partner: {str(e)}",
                    "execution_log": execution_log,
                    "completed_steps": [],
                }

            # Create address for business partner
            execution_log.append("\n📍 Processing Address...")
            address_id, addr_log = self._create_address(
                bp_id, invoice.address, etendo_url, token
            )
            execution_log.extend(addr_log)

            # Create sales invoice header - CRITICAL: must succeed
            execution_log.append("\n📝 Creating Invoice Header...")
            try:
                invoice_id, inv_log = self._create_invoice_header(
                    invoice, bp_id, address_id, etendo_url, token
                )
                execution_log.extend(inv_log)
            except Exception as e:
                execution_log.append(
                    f"\n❌ CRITICAL ERROR: Failed to create Invoice Header: {str(e)}"
                )
                copilot_debug(f"Critical error creating invoice header: {str(e)}")
                return {
                    "status": "error",
                    "error": f"Failed to create Invoice Header: {str(e)}",
                    "execution_log": execution_log,
                    "completed_steps": [
                        {"business_partner_id": bp_id},
                        {"address_id": address_id},
                    ],
                }

            # Create invoice lines
            execution_log.append("\n📦 Creating Invoice Lines...")
            line_ids, lines_log = self._create_invoice_lines(
                invoice_id, invoice.lines, etendo_url, token
            )
            execution_log.extend(lines_log)

            execution_log.append("\n✅ Invoice created successfully!")
            execution_log.append(f"🆔 Invoice ID: {invoice_id}")
            execution_log.append(f"📊 Total lines created: {len(line_ids)}")

            result = {
                "status": "success",
                "invoice_id": invoice_id,
                "businesspartner_id": bp_id,
                "address_id": address_id,
                "line_ids": line_ids,
                "execution_log": execution_log,
                "message": f"Sales invoice {invoice_id} created successfully with {len(line_ids)} lines",
            }

            return result

        except Exception as e:
            copilot_debug(f"Error in SalesInvoiceCreationTool: {str(e)}")
            execution_log.append(f"\n❌ Error: {str(e)}")
            return {"status": "error", "error": str(e), "execution_log": execution_log}

    def _process_businesspartner(
        self, invoice: InvoiceSchema, etendo_url: str, token: str
    ) -> tuple:
        """
        Detect or create business partner.

        1. Search by CIF if available
        2. If not found, search by name using SimSearch
        3. If still not found, create new BP

        Returns:
            tuple: (Business Partner ID, log entries)
        """
        print("\n--- Processing Business Partner ---")
        log = []

        # Normalize CIF value - treat "NULL" string and empty strings as None
        cif_value = invoice.cif
        if cif_value and isinstance(cif_value, str):
            cif_value = cif_value.strip()
            if cif_value.upper() == "NULL" or cif_value == "":
                cif_value = None

        # Search by CIF if available
        if cif_value:
            log.append(f"  🔍 Searching by CIF: {cif_value}")
            bp_id = self._search_bp_by_cif(cif_value, etendo_url, token)
            if bp_id:
                print(f"Business Partner found by CIF: {bp_id}")
                log.append(f"  ✓ Found by CIF: {bp_id}")
                return (bp_id, log)
            else:
                log.append("  ✗ Not found by CIF")
        else:
            if invoice.cif:
                log.append(f"  ⚠ Invalid CIF value ('{invoice.cif}'), skipping CIF search")

        # If not found, create new BP
        print("Business Partner not found. Creating new one...")
        log.append("  ➕ Creating new Business Partner...")
        
        # For creation, use the normalized CIF value
        invoice_copy = invoice.model_copy()
        invoice_copy.cif = cif_value
        
        bp_id = self._create_businesspartner(invoice_copy, etendo_url, token)
        print(f"Business Partner created: {bp_id}")
        log.append(f"  ✓ Created: {bp_id}")
        log.append(f"     - Name: {invoice.businesspartner}")
        if cif_value:
            log.append(f"     - CIF: {cif_value}")
        else:
            log.append("     - CIF: (not provided)")
        return (bp_id, log)

    def _search_bp_by_cif(self, cif: str, etendo_url: str, token: str) -> Optional[str]:
        """Search Business Partner by CIF using Etendo API."""
        print(f"Searching BP by CIF: {cif}")

        try:
            # Query BusinessPartner entity filtering by tax ID
            endpoint = (
                f"/sws/com.etendoerp.etendorx.datasource/BusinessPartner"
                f"?q=taxID=={cif}&_startRow=0&_endRow=1"
            )

            data = call_etendo(
                url=etendo_url,
                method="GET",
                endpoint=endpoint,
                access_token=token,
                body_params={},
            )

            if data and data.get("response", {}).get("data"):
                bp_data = data["response"]["data"][0]
                return bp_data.get("id")

            return None

        except Exception as e:
            copilot_debug(f"Error searching BP by CIF: {str(e)}")
            return None

    def _create_businesspartner(
        self, invoice: InvoiceSchema, etendo_url: str, token: str
    ) -> str:
        """Create a new Business Partner in Etendo."""
        print(f"Creating Business Partner: {invoice.businesspartner}")

        # CIF is mandatory for creating a new BP
        if not invoice.cif:
            raise ToolException(
                "CIF/Tax ID is required to create a new Business Partner"
            )

        try:
            import uuid

            endpoint = "/sws/com.etendoerp.etendorx.datasource/BusinessPartner"

            # Generate unique searchKey using CIF and timestamp/UUID to avoid duplicates
            unique_suffix = str(uuid.uuid4())[:8]
            documentno = f"{invoice.cif}_{unique_suffix}"

            # Prepare payload with required fields
            payload = {
                "name": invoice.businesspartner,
                "searchKey": documentno,
                "taxID": invoice.cif,
                "customer": True,  # Mark as customer for sales invoices
            }

            copilot_debug(f"Creating BP with payload: {json.dumps(payload, indent=2)}")

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            if data:
                bp_data = data.get("response", {}).get("data", [{}])[0]
                bp_id = bp_data.get("id")

                # Configure BP as customer with price list, payment method, etc.
                self._configure_bp_customer(bp_id, etendo_url, token)

                print(f"Business Partner created successfully: {bp_id}")
                
                
                
                return bp_id
            else:
                raise ToolException(
                    "Failed to create Business Partner: no response data"
                )

        except ToolException:
            raise
        except Exception as e:
            copilot_debug(f"Error creating Business Partner: {str(e)}")
            raise ToolException(f"Failed to create Business Partner: {str(e)}")

    def _configure_bp_customer(
        self, bp_id: str, etendo_url: str, token: str
    ) -> None:
        """
        Configure Business Partner as customer with price list, payment method, and payment terms.
        Uses BPCustomer endpoint to update the BP with customer-specific fields.
        
        Args:
            bp_id: Business Partner ID
            etendo_url: Etendo URL
            token: Access token
        """
        print(f"Configuring Business Partner as customer: {bp_id}")
        
        try:
            # BPCustomer endpoint updates the BusinessPartner with customer fields
            # Use PUT method with the BP ID in the URL
            endpoint = f"/sws/com.etendoerp.etendorx.datasource/BPCustomer/{bp_id}"
            
            # Prepare payload with customer configuration
            payload = {
                "priceList": "AEE66281A08F42B6BC509B8A80A33C29",
                "paymentMethod": "47506D4260BA4996B92768FF609E6665",
                "paymentTerms": "A8EB69EF071A43DDBFF1A796B59E5B1D",
            }
            
            copilot_debug(f"Updating BPCustomer with payload: {json.dumps(payload, indent=2)}")
            
            data = call_etendo(
                url=etendo_url,
                method="PUT",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )
            
            if data:
                print(f"BP Customer configuration updated successfully")
            else:
                # Log warning but don't fail the entire process
                print("Warning: Failed to configure BP Customer, but continuing...")
                copilot_debug("Failed to configure BP Customer: no response data")
                
        except Exception as e:
            # Log error but don't fail the entire BP creation process
            print(f"Warning: Could not configure BP Customer: {str(e)}")
            copilot_debug(f"Error configuring BP Customer: {str(e)}")

    def _create_address(
        self, bp_id: str, address: Optional[InvoiceAddress], etendo_url: str, token: str
    ) -> tuple:
        """
        Create billing address for the business partner.
        Always creates a new address marked as billing address.

        Steps:
        1. Create Location with address data using LocationCreatorWebhook
        2. Create BPAddress linking BP to Location
        3. Mark as invoice and shipping address

        Returns:
            tuple: (BPAddress ID, log entries)
        """
        print(f"\n--- Creating Address for BP: {bp_id} ---")
        log = []

        if not address:
            print("No address provided, skipping address creation")
            log.append("  ⊘ No address data provided, skipped")
            return ("NO_ADDRESS", log)

        try:
            # Step 1: Create Location
            log.append("  📍 Creating Location...")
            location_id = self._create_location(address, etendo_url, token)
            log.append(f"  ✓ Location created: {location_id}")

            if address.city:
                log.append(f"     - City: {address.city}")
            if address.postal_code:
                log.append(f"     - Postal Code: {address.postal_code}")

            # Step 2: Create BusinessPartnerLocation (link BP with Location)
            log.append("  🔗 Linking address to Business Partner...")
            bp_location_id = self._create_bp_location(
                bp_id, location_id, etendo_url, token
            )
            log.append(f"  ✓ Address linked: {bp_location_id}")

            print(f"Address created and linked successfully: {bp_location_id}")
            return (bp_location_id, log)

        except Exception as e:
            copilot_debug(f"Error creating address: {str(e)}")
            # Address creation is not critical, we can continue without it
            print(f"Warning: Could not create address: {str(e)}")
            log.append(f"  ⚠ Warning: Address creation failed: {str(e)}")
            return ("ADDRESS_CREATION_FAILED", log)

    def _create_location(
        self, address: InvoiceAddress, etendo_url: str, token: str
    ) -> str:
        """
        Create a Location record with address data using LocationCreatorWebhook.

        Returns:
            str: Location ID
        """
        print("Creating Location...")

        try:
            endpoint = "/webhooks/LocationCreatorWebhook"

            # Prepare payload following LocationCreatorWebhook spec
            # Required fields: Address1, CountryISOCode, City, Postal
            payload = {
                "Address1": address.street or ".",
                "City": address.city or ".",
                "Postal": address.postal_code or ".",
                "CountryISOCode": "ES",  # Default to Spain, should be 2-char ISO code
            }

            # Override country if provided (assume it's ISO code or convert if needed)
            if address.country:
                # If country is already 2 chars, use it; otherwise keep default
                if len(address.country) == 2:
                    payload["CountryISOCode"] = address.country.upper()

            copilot_debug(
                f"Creating Location with payload: {json.dumps(payload, indent=2)}"
            )

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            if data:
                # Webhook returns LocationID in the response
                location_id = data.get("LocationID")
                if not location_id:
                    # Try alternative response structures
                    location_id = (
                        data.get("id")
                        or data.get("ID")
                        or data.get("response", {}).get("id")
                    )

                if location_id:
                    print(f"Location created: {location_id}")
                    return location_id
                else:
                    raise ToolException(
                        f"Failed to get Location ID from response: {data}"
                    )
            else:
                raise ToolException("Failed to create Location: no response data")

        except Exception as e:
            copilot_debug(f"Error creating Location: {str(e)}")
            raise ToolException(f"Failed to create Location: {str(e)}")

    def _create_bp_location(
        self, bp_id: str, location_id: str, etendo_url: str, token: str
    ) -> str:
        """
        Create BPAddress linking BP to Location.
        Marks it as invoice and shipping address.

        Returns:
            str: BPAddress ID
        """
        print("Creating BPAddress link...")

        try:
            endpoint = "/sws/com.etendoerp.etendorx.datasource/BPAddress"

            # Link BP with Location following BPAddress spec
            payload = {
                "businessPartner": bp_id,
                "locationAddress": location_id,  # Note: field name is locationAddress, not location
                "name": ".",  # Descriptive name, using "." as default
                "invoiceToAddress": True,  # Mark as billing/invoice address
                "shipToAddress": True,  # Also mark as shipping address for new BP
            }

            copilot_debug(
                f"Creating BPAddress with payload: {json.dumps(payload, indent=2)}"
            )

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            if data:
                bp_address_data = data.get("response", {}).get("data", [{}])[0]
                bp_address_id = bp_address_data.get("id")
                print(f"BPAddress created: {bp_address_id}")
                return bp_address_id
            else:
                raise ToolException("Failed to create BPAddress: no response data")

        except Exception as e:
            copilot_debug(f"Error creating BPAddress: {str(e)}")
            raise ToolException(f"Failed to create BPAddress: {str(e)}")

    def _create_invoice_header(
        self,
        invoice: InvoiceSchema,
        bp_id: str,
        address_id: str,
        etendo_url: str,
        token: str,
    ) -> tuple:
        """
        Create the sales invoice header.

        Returns:
            tuple: (Invoice ID, log entries)
        """
        print("\n--- Creating Invoice Header ---")
        log = []

        try:
            endpoint = "/sws/com.etendoerp.etendorx.datasource/SalesInvoice"

            # Prepare payload - only send fields we want to set
            payload = {
                "businessPartner": bp_id,
                "invoiceDate": invoice.date or "",
            }

            # Add optional fields only if they have values
            if invoice.documentno:
                payload["documentNo"] = invoice.documentno
                log.append(f"  📄 Document No: {invoice.documentno}")

            if invoice.businesspartner:
                payload["description"] = f"Invoice for {invoice.businesspartner}"

            log.append(f"  📅 Invoice Date: {invoice.date or 'Not specified'}")
            log.append(f"  👤 Business Partner: {bp_id}")

            copilot_debug(
                f"Creating invoice with payload: {json.dumps(payload, indent=2)}"
            )

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            if data:
                invoice_data = data.get("response", {}).get("data", [{}])[0]
                invoice_id = invoice_data.get("id")
                print(f"Invoice header created: {invoice_id}")
                log.append(f"  ✓ Invoice header created: {invoice_id}")
                return (invoice_id, log)
            else:
                raise ToolException("Failed to create invoice: no response data")

        except Exception as e:
            copilot_debug(f"Error creating invoice header: {str(e)}")
            raise

    def _create_invoice_lines(
        self, invoice_id: str, lines: list, etendo_url: str, token: str
    ) -> tuple:
        """
        Create invoice lines for the sales invoice.

        Returns:
            tuple: (list of line IDs, log entries)
        """
        print("\n--- Creating Invoice Lines ---")
        log = []
        line_ids = []

        for idx, line in enumerate(lines, 1):
            print(f"\nProcessing line {idx}: {line.product}")
            log.append(f"\n  Line {idx}: {line.product}")

            # Search for product (returns tuple: product_id, original_name)
            product_id, original_name = self._search_product(
                line.product, etendo_url, token
            )

            if original_name:
                # Generic product was used
                log.append("    ⚠ Product not found, using generic product")
                log.append(f"    📝 Original product: {original_name}")
            else:
                log.append(f"    ✓ Product found: {product_id}")

            # Get tax ID
            tax_id = self._get_tax_id(line.tax_rate, etendo_url, token)
            if tax_id:
                log.append(f"    💰 Tax rate: {line.tax_rate}% (ID: {tax_id})")
            else:
                log.append("    💰 Tax rate: System auto-select")

            # Create the line
            log.append(
                f"    📊 Quantity: {line.quantity}, Unit Price: {line.unit_price}"
            )
            line_id = self._create_invoice_line(
                invoice_id, product_id, line, tax_id, original_name, etendo_url, token
            )
            line_ids.append(line_id)
            log.append(f"    ✓ Line created: {line_id}")

        print(f"\nCreated {len(line_ids)} invoice lines")
        return (line_ids, log)

    def _search_product(self, product_name: str, etendo_url: str, token: str) -> tuple:
        """
        Search for product using SimSearch.
        If not found, search for "Producto Generico".

        Returns:
            tuple: (product_id, original_product_name or None)
                   original_product_name is set only when generic product is used
        """
        if not product_name:
            generic_id = self._get_generic_product(etendo_url, token)
            return (generic_id, None)

        print(f"Searching product: {product_name}")

        try:
            endpoint = SIMSEARCH_ENDPOINT
            payload = {
                "entityName": "Product",
                "items": [product_name],
                "minSimPercent": 70,
                "qtyResults": 1,
            }

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            # SimSearch returns results in message field as JSON string
            if data and data.get("message"):
                import json

                message_data = json.loads(data["message"])
                # Results are in item_0, item_1, etc.
                if "item_0" in message_data:
                    items = message_data["item_0"].get("data", [])
                    if items and len(items) > 0:
                        best_match = items[0]
                        product_id = best_match.get("id")
                        print(f"Product found: {product_id}")
                        return (product_id, None)

            # Product not found, use generic product
            print(f"Product '{product_name}' not found, using generic product")
            generic_id = self._get_generic_product(etendo_url, token)
            return (generic_id, product_name)

        except Exception as e:
            copilot_debug(f"Error searching product: {str(e)}")
            generic_id = self._get_generic_product(etendo_url, token)
            return (generic_id, product_name)

    def _get_generic_product(self, etendo_url: str, token: str) -> str:
        """
        Search for "Producto Generico" using SimSearch.
        Raises ToolException if not found.
        """
        print('Searching for "Producto Generico"')

        try:
            endpoint = SIMSEARCH_ENDPOINT
            payload = {
                "entityName": "Product",
                "items": ["Producto Generico"],
                "minSimPercent": 70,
                "qtyResults": 1,
            }

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            # SimSearch returns results in message field as JSON string
            if data and data.get("message"):
                import json

                message_data = json.loads(data["message"])
                # Results are in item_0, item_1, etc.
                if "item_0" in message_data:
                    items = message_data["item_0"].get("data", [])
                    if items and len(items) > 0:
                        best_match = items[0]
                        product_id = best_match.get("id")
                        print(f"Generic product found: {product_id}")
                        return product_id

            # If generic product not found, fail
            raise ToolException(
                'Generic product "Producto Generico" not found in the system. '
                "Please ensure the generic product is configured."
            )

        except ToolException:
            raise
        except Exception as e:
            copilot_debug(f"Error getting generic product: {str(e)}")
            raise ToolException(f"Failed to search for generic product: {str(e)}")

    def _get_tax_id(
        self, tax_rate: Optional[float], etendo_url: str, token: str
    ) -> Optional[str]:
        """
        Get tax ID based on tax rate percentage.

        Searches for a TaxRate record matching the given rate with criteria:
        - parentTaxRate must be null
        - salesPurchaseType must be "S" (Sales)
        - Prioritizes names starting with "Entregas"

        If not found or no rate provided, returns None (system will auto-select).

        Returns:
            str or None: Tax ID if found, None otherwise
        """
        if not tax_rate:
            print("No tax rate provided, system will auto-select")
            return None

        print(f"Searching tax ID for rate: {tax_rate}%")

        try:
            # Search with all criteria: rate, parentTaxRate=null, salesPurchaseType=S
            endpoint = (
                f"/sws/com.etendoerp.etendorx.datasource/TaxRate"
                f"?q=rate=={tax_rate};parentTaxRate=is=null;salesPurchaseType==S"
                f"&_startRow=0&_endRow=10"
            )

            data = call_etendo(
                url=etendo_url,
                method="GET",
                endpoint=endpoint,
                access_token=token,
                body_params={},
            )

            if data and data.get("response", {}).get("data"):
                results = data["response"]["data"]

                # Prioritize taxes starting with "Entregas"
                entregas_taxes = [
                    tax for tax in results if tax.get("name", "").startswith("Entregas")
                ]

                if entregas_taxes:
                    tax_id = entregas_taxes[0].get("id")
                    tax_name = entregas_taxes[0].get("name")
                    print(f"Tax rate found (Entregas priority): {tax_name} - {tax_id}")
                    return tax_id
                elif results:
                    # If no "Entregas" tax, use first result
                    tax_id = results[0].get("id")
                    tax_name = results[0].get("name")
                    print(f"Tax rate found: {tax_name} - {tax_id}")
                    return tax_id
                else:
                    print(f"No tax rate found for {tax_rate}%, system will auto-select")
                    return None
            else:
                print(f"No tax rate found for {tax_rate}%, system will auto-select")
                return None

        except Exception as e:
            copilot_debug(f"Error searching tax rate: {str(e)}")
            print("Warning: Could not search tax rate, system will auto-select")
            return None

    def _create_invoice_line(
        self,
        invoice_id: str,
        product_id: str,
        line: InvoiceLine,
        tax_id: Optional[str],
        original_product_name: Optional[str],
        etendo_url: str,
        token: str,
    ) -> str:
        """
        Create a single invoice line.

        Args:
            invoice_id: Invoice ID
            product_id: Product ID to use
            line: Invoice line data
            tax_id: Tax ID (optional)
            original_product_name: Original product name if generic product was used
            etendo_url: Etendo URL
            token: Access token
        """
        try:
            endpoint = "/sws/com.etendoerp.etendorx.datasource/SalesInvoiceLine"

            payload = {
                "invoice": invoice_id,
                "product": product_id,
                "invoicedQuantity": str(line.quantity or 1),
                "unitPrice": line.unit_price or 0,
            }

            # Add tax if available (if None, system will auto-select)
            if tax_id:
                payload["tax"] = tax_id

            # Add description - use original product name if generic was used
            if original_product_name:
                # Generic product was used, save original name in description
                payload["description"] = f"Producto solicitado: {original_product_name}"
                print(f"Using generic product for: {original_product_name}")
            elif line.product:
                # Product found, use product name as description
                payload["description"] = line.product

            copilot_debug(
                f"Creating line with payload: {json.dumps(payload, indent=2)}"
            )

            data = call_etendo(
                url=etendo_url,
                method="POST",
                endpoint=endpoint,
                access_token=token,
                body_params=payload,
            )

            if data:
                line_data = data.get("response", {}).get("data", [{}])[0]
                line_id = line_data.get("id")
                print(f"Invoice line created: {line_id}")
                return line_id
            else:
                raise ToolException("Failed to create invoice line: no response data")

        except Exception as e:
            copilot_debug(f"Error creating invoice line: {str(e)}")
            raise
