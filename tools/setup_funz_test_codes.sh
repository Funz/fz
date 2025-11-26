#!/bin/bash
# Setup script for Funz calculator test CODE configurations
# Creates the calc.sh, calc_product.sh, and calc_fail.sh scripts
# and configures calculator XML files with CODE elements
#
# Usage:
#   ./setup_funz_test_codes.sh [install_dir]
#
# Default install directory: ~/.funz_calculator

set -e  # Exit on error

# Configuration
INSTALL_DIR="${1:-$HOME/.funz_calculator}"
DIST_DIR="$INSTALL_DIR/funz-calculator/dist"

echo "======================================================================="
echo " Funz Calculator Test CODE Setup"
echo "======================================================================="
echo ""
echo "Install Dir: $INSTALL_DIR"
echo "Dist Dir: $DIST_DIR"
echo ""

# Check if dist directory exists
if [ ! -d "$DIST_DIR" ]; then
    echo "❌ Funz calculator not found at: $DIST_DIR"
    echo ""
    echo "Run setup first:"
    echo "  tools/setup_funz_calculator.sh"
    exit 1
fi

cd "$DIST_DIR"

# Create calc.sh - performs addition (a + b)
echo "📝 Creating calc.sh..."
cat > calc.sh << 'EOF'
#!/bin/bash
# Read input
source input.txt

# Calculate result (a + b)
result=$(echo "$a + $b" | bc)

# Write output
echo "result = $result" > output.txt
EOF
chmod +x calc.sh
echo "✓ Created: $DIST_DIR/calc.sh"

# Create calc_product.sh - performs multiplication (x * y)
echo "📝 Creating calc_product.sh..."
cat > calc_product.sh << 'EOF'
#!/bin/bash
# Read input
source input.txt

# Calculate result (x * y)
result=$(echo "$x * $y" | bc)

# Write output
echo "product = $result" > output.txt
EOF
chmod +x calc_product.sh
echo "✓ Created: $DIST_DIR/calc_product.sh"

# Create calc_fail.sh - always fails for error testing
echo "📝 Creating calc_fail.sh..."
cat > calc_fail.sh << 'EOF'
#!/bin/bash
# This script always fails to test error handling
echo "Error: Simulated calculation failure" >&2
exit 1
EOF
chmod +x calc_fail.sh
echo "✓ Created: $DIST_DIR/calc_fail.sh"

echo ""

# Function to create/update calculator XML with CODE elements
create_calculator_xml() {
    local port=$1
    local xml_file="calculator-${port}.xml"

    echo "📝 Creating $xml_file..."

    cat > "$xml_file" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<CALCULATOR name="calc-${port}" spool="spool-${port}">
  <HOST name="localhost" port="${port}" />
  <CODE name="bash" command="/bin/bash" />
  <CODE name="sh" command="/bin/sh" />
  <CODE name="shell" command="/bin/bash" />
  <CODE name="calc" command="/bin/bash $DIST_DIR/calc.sh" />
  <CODE name="calc_product" command="/bin/bash $DIST_DIR/calc_product.sh" />
EOF

    # Only add calc_fail to port 5555
    if [ "$port" = "5555" ]; then
        cat >> "$xml_file" << EOF
  <CODE name="calc_fail" command="/bin/bash $DIST_DIR/calc_fail.sh" />
EOF
    fi

    cat >> "$xml_file" << EOF
</CALCULATOR>
EOF

    echo "✓ Created: $DIST_DIR/$xml_file"
}

# Create XML configurations for 3 calculator ports
create_calculator_xml 5555
create_calculator_xml 5556
create_calculator_xml 5557

echo ""
echo "======================================================================="
echo " ✅ Test CODE Setup Complete"
echo "======================================================================="
echo ""
echo "Created scripts:"
echo "  - calc.sh (addition: a + b)"
echo "  - calc_product.sh (multiplication: x * y)"
echo "  - calc_fail.sh (always fails for error testing)"
echo ""
echo "Created calculator configs:"
echo "  - calculator-5555.xml (with calc, calc_product, calc_fail CODEs)"
echo "  - calculator-5556.xml (with calc, calc_product CODEs)"
echo "  - calculator-5557.xml (with calc, calc_product CODEs)"
echo ""
echo "Next steps:"
echo "  1. Start calculators:"
echo "     tools/start_funz_calculator.sh 5555"
echo "     tools/start_funz_calculator.sh 5556"
echo "     tools/start_funz_calculator.sh 5557"
echo ""
echo "  2. Run integration tests:"
echo "     python -m pytest tests/test_funz_integration.py -v"
echo ""
