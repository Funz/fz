#!/bin/bash
# Setup script for Funz calculator infrastructure
# Downloads and builds funz-profile, funz-core, and funz-calculator
#
# Usage:
#   ./setup_funz_calculator.sh [install_dir]
#
# Default install directory: ~/.funz_calculator

set -e  # Exit on error

# Configuration
INSTALL_DIR="${1:-$HOME/.funz_calculator}"
FUNZ_PROFILE_REPO="https://github.com/Funz/funz-profile.git"
FUNZ_CORE_REPO="https://github.com/Funz/funz-core.git"
FUNZ_CALCULATOR_REPO="https://github.com/Funz/funz-calculator.git"

echo "======================================================================="
echo " Funz Calculator Setup"
echo "======================================================================="
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
MISSING_TOOLS=""

if ! command -v git &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS git"
fi

if ! command -v ant &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS ant"
fi

if ! command -v java &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS java"
fi

if ! command -v javac &> /dev/null; then
    MISSING_TOOLS="$MISSING_TOOLS javac"
fi

if [ -n "$MISSING_TOOLS" ]; then
    echo "❌ Missing required tools:$MISSING_TOOLS"
    echo ""
    echo "Install on Ubuntu/Debian:"
    echo "  sudo apt-get install -y git ant openjdk-11-jdk"
    echo ""
    echo "Install on macOS:"
    echo "  brew install git ant openjdk@11"
    echo ""
    exit 1
fi

echo "✓ All prerequisites available"
echo ""

# Create installation directory
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Clone and build funz-profile
echo "======================================================================="
echo " Step 1/3: funz-profile"
echo "======================================================================="
if [ -d "funz-profile" ]; then
    echo "⏭️  funz-profile already exists, skipping clone"
else
    echo "📦 Cloning funz-profile..."
    git clone "$FUNZ_PROFILE_REPO"
    echo "✓ Cloned"
fi

export FUNZ_PROFILE_HOME="$INSTALL_DIR/funz-profile"
echo "✓ FUNZ_PROFILE_HOME=$FUNZ_PROFILE_HOME"
echo ""

# Clone and build funz-core
echo "======================================================================="
echo " Step 2/3: funz-core"
echo "======================================================================="
if [ -d "funz-core/dist" ]; then
    echo "⏭️  funz-core dist already exists, skipping build"
else
    if [ -d "funz-core" ]; then
        echo "📦 Rebuilding funz-core..."
        cd funz-core
    else
        echo "📦 Cloning funz-core..."
        git clone "$FUNZ_CORE_REPO"
        cd funz-core
    fi

    echo "🔨 Building with ant..."
    ant clean dist
    cd ..
    echo "✓ Built"
fi

export FUNZ_CORE_HOME="$INSTALL_DIR/funz-core"
echo "✓ FUNZ_CORE_HOME=$FUNZ_CORE_HOME"
echo ""

# Clone and build funz-calculator
echo "======================================================================="
echo " Step 3/3: funz-calculator"
echo "======================================================================="
if [ -d "funz-calculator/dist" ]; then
    echo "⏭️  funz-calculator dist already exists, skipping build"
else
    if [ -d "funz-calculator" ]; then
        echo "📦 Rebuilding funz-calculator..."
        cd funz-calculator
    else
        echo "📦 Cloning funz-calculator..."
        git clone "$FUNZ_CALCULATOR_REPO"
        cd funz-calculator
    fi

    echo "🔨 Building with ant..."
    ant clean dist
    cd ..
    echo "✓ Built"
fi

export FUNZ_CALCULATOR_HOME="$INSTALL_DIR/funz-calculator"
echo "✓ FUNZ_CALCULATOR_HOME=$FUNZ_CALCULATOR_HOME"
echo ""

# Create environment file
ENV_FILE="$INSTALL_DIR/funz_env.sh"
cat > "$ENV_FILE" << EOF
# Funz Calculator Environment
# Source this file: source $ENV_FILE

export FUNZ_PROFILE_HOME="$INSTALL_DIR/funz-profile"
export FUNZ_CORE_HOME="$INSTALL_DIR/funz-core"
export FUNZ_CALCULATOR_HOME="$INSTALL_DIR/funz-calculator"

# Add to PATH
export PATH="\$FUNZ_CALCULATOR_HOME/dist:\$PATH"

echo "Funz environment loaded:"
echo "  FUNZ_PROFILE_HOME=\$FUNZ_PROFILE_HOME"
echo "  FUNZ_CORE_HOME=\$FUNZ_CORE_HOME"
echo "  FUNZ_CALCULATOR_HOME=\$FUNZ_CALCULATOR_HOME"
EOF

chmod +x "$ENV_FILE"
echo "✓ Created environment file: $ENV_FILE"
echo ""

# Summary
echo "======================================================================="
echo " ✅ Setup Complete"
echo "======================================================================="
echo ""
echo "Installation: $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "  1. Source environment (optional):"
echo "     source $ENV_FILE"
echo ""
echo "  2. Start calculator daemon:"
echo "     $INSTALL_DIR/../start_funz_calculator.sh [udp_port]"
echo ""
echo "  3. Or use the helper scripts in tools/"
echo ""
echo "Directory structure:"
echo "  $INSTALL_DIR/"
echo "  ├── funz-profile/     # Profile definitions"
echo "  ├── funz-core/        # Core library"
echo "  │   └── dist/         # Built JARs"
echo "  ├── funz-calculator/  # Calculator daemon"
echo "  │   └── dist/         # Calculator executable"
echo "  └── funz_env.sh       # Environment variables"
echo ""
