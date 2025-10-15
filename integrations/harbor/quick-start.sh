#!/bin/bash
set -e

# Harbor Integration Quick Start Script
# This script helps you set up and run the Harbor integration from scratch

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Harbor Integration for Port - Quick Start${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to print status
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Step 1: Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"

if ! command_exists python3; then
    print_error "Python 3 is not installed. Please install Python 3.12 or later."
    exit 1
fi
print_status "Python 3 is installed"

if ! command_exists poetry; then
    print_error "Poetry is not installed. Install it with: curl -sSL https://install.python-poetry.org | python3 -"
    exit 1
fi
print_status "Poetry is installed"

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker Desktop."
    exit 1
fi
print_status "Docker is installed"

if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
print_status "Docker is running"

# Step 2: Install dependencies
echo -e "\n${BLUE}Step 2: Installing integration dependencies...${NC}"
if [ ! -d ".venv" ]; then
    make install
    print_status "Dependencies installed"
else
    print_status "Virtual environment already exists"
fi

# Step 3: Check for Harbor
echo -e "\n${BLUE}Step 3: Checking for Harbor instance...${NC}"
if curl -s http://localhost:8081/api/v2.0/systeminfo >/dev/null 2>&1; then
    print_status "Harbor is running at http://localhost:8081"
else
    print_warning "Harbor is not running locally"
    echo -e "Would you like to set up Harbor locally? (y/n)"
    read -r setup_harbor

    if [ "$setup_harbor" = "y" ]; then
        echo -e "\n${BLUE}Setting up Harbor locally...${NC}"

        # Create Harbor directory
        HARBOR_DIR="$HOME/harbor-test"
        mkdir -p "$HARBOR_DIR"
        cd "$HARBOR_DIR"

        # Download Harbor (if not already downloaded)
        if [ ! -f "harbor-offline-installer-v2.10.0.tgz" ]; then
            echo "Downloading Harbor installer..."
            curl -LO https://github.com/goharbor/harbor/releases/download/v2.10.0/harbor-offline-installer-v2.10.0.tgz
            print_status "Harbor installer downloaded"
        fi

        # Extract (if not already extracted)
        if [ ! -d "harbor" ]; then
            echo "Extracting Harbor..."
            tar xzf harbor-offline-installer-v2.10.0.tgz
            print_status "Harbor extracted"
        fi

        cd harbor

        # Configure Harbor
        if [ ! -f "harbor.yml" ]; then
            cp harbor.yml.tmpl harbor.yml
            # Configure for local use
            sed -i.bak 's/hostname: reg.mydomain.com/hostname: localhost/' harbor.yml
            sed -i.bak 's/port: 80/port: 8081/' harbor.yml
            sed -i.bak 's/harbor_admin_password: Harbor12345/harbor_admin_password: Harbor12345/' harbor.yml
            print_status "Harbor configured"
        fi

        # Install Harbor
        echo "Installing Harbor (this may take a few minutes)..."
        sudo ./install.sh --with-trivy
        print_status "Harbor installed and running"

        # Return to integration directory
        cd -
    else
        print_warning "Skipping Harbor setup. Make sure you have access to a Harbor instance."
    fi
fi

# Step 4: Set up environment variables
echo -e "\n${BLUE}Step 4: Setting up environment variables...${NC}"
if [ ! -f ".env.local" ]; then
    echo "Creating .env.local file..."

    # Prompt for Port credentials
    echo -e "\n${YELLOW}Port API Credentials${NC}"
    echo "Get these from: https://app.getport.io/settings/credentials"
    read -p "Port Client ID: " PORT_CLIENT_ID
    read -sp "Port Client Secret: " PORT_CLIENT_SECRET
    echo ""

    # Create .env.local
    cat > .env.local << EOF
# Port API Credentials
PORT_CLIENT_ID=$PORT_CLIENT_ID
PORT_CLIENT_SECRET=$PORT_CLIENT_SECRET

# Harbor Credentials
HARBOR_BASE_URL=http://localhost:8081/api/v2.0
HARBOR_ADMIN_USER=admin
HARBOR_ADMIN_PASS=Harbor12345

# Optional
PORT_ORG_ID=my-organization
EOF

    print_status ".env.local created"
else
    print_status ".env.local already exists"
fi

# Load environment variables
set -a
source .env.local
set +a

# Step 5: Create test data in Harbor
echo -e "\n${BLUE}Step 5: Creating test data in Harbor...${NC}"
if curl -s http://localhost:8081/api/v2.0/systeminfo >/dev/null 2>&1; then
    # Create project
    if ! curl -s -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASS" \
        "http://localhost:8081/api/v2.0/projects/opensource" >/dev/null 2>&1; then

        echo "Creating 'opensource' project..."
        curl -X POST "http://localhost:8081/api/v2.0/projects" \
            -u "$HARBOR_ADMIN_USER:$HARBOR_ADMIN_PASS" \
            -H "Content-Type: application/json" \
            -d '{
                "project_name": "opensource",
                "metadata": {"public": "true"}
            }' >/dev/null 2>&1
        print_status "Project 'opensource' created"
    else
        print_status "Project 'opensource' already exists"
    fi

    # Push test image
    echo "Pushing test image to Harbor..."
    docker pull alpine:latest >/dev/null 2>&1
    docker tag alpine:latest localhost:8081/opensource/alpine:latest
    docker login localhost:8081 -u "$HARBOR_ADMIN_USER" -p "$HARBOR_ADMIN_PASS" >/dev/null 2>&1
    docker push localhost:8081/opensource/alpine:latest >/dev/null 2>&1
    print_status "Test image pushed"
else
    print_warning "Skipping test data creation (Harbor not accessible)"
fi

# Step 6: Create config.yaml
echo -e "\n${BLUE}Step 6: Creating configuration file...${NC}"
if [ ! -f "config.yaml" ]; then
    cp examples/config.sample.yaml config.yaml

    # Update with local values
    sed -i.bak 's|https://harbor.example.com/api/v2.0|http://localhost:8081/api/v2.0|' config.yaml
    sed -i.bak 's|authMode: robot_token|authMode: basic|' config.yaml
    sed -i.bak 's|projects: \["platform", "sre"\]|projects: "opensource"|' config.yaml

    print_status "config.yaml created"
else
    print_status "config.yaml already exists"
fi

# Step 7: Run validation
echo -e "\n${BLUE}Step 7: Running integration validation...${NC}"
source .venv/bin/activate

echo "Running dry-run validation..."
if ocean sail --validate 2>&1 | tee validation.log; then
    print_status "Validation completed successfully!"

    echo -e "\n${GREEN}========================================${NC}"
    echo -e "${GREEN}Setup Complete!${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    echo -e "Next steps:"
    echo -e "1. Review validation output above"
    echo -e "2. Create blueprints in Port: https://app.getport.io/settings/data-model"
    echo -e "3. Run full sync: ${BLUE}ocean sail${NC}"
    echo -e "4. View your data: https://app.getport.io\n"

    echo -e "${YELLOW}Quick commands:${NC}"
    echo -e "  ${BLUE}source .venv/bin/activate${NC}  - Activate virtual environment"
    echo -e "  ${BLUE}ocean sail --validate${NC}       - Test without syncing"
    echo -e "  ${BLUE}ocean sail${NC}                  - Run full sync"
    echo -e "  ${BLUE}make test${NC}                   - Run unit tests\n"

else
    print_error "Validation failed. Check validation.log for details."
    exit 1
fi
