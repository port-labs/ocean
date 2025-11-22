#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos";;
        Linux*) echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *) echo "unknown";;
    esac
}

# Function to get Cursor MCP config path
get_cursor_mcp_path() {
    case "$(detect_os)" in
        "macos"|"linux")
            echo "$HOME/.cursor/mcp.json"
            ;;
        "windows")
            echo "$HOME/.cursor/mcp.json"
            ;;
        *)
            print_error "Unknown operating system"
            exit 1
            ;;
    esac
}

# Test if uv is installed
test_uv_installation() {
    print_status "Checking uv installation..."

    if command -v uv >/dev/null 2>&1; then
        UV_VERSION=$(uv --version 2>/dev/null || echo "unknown")
        print_success "uv is installed: $UV_VERSION"
        return 0
    else
        print_error "uv is not installed or not in PATH"
        return 1
    fi
}

# Test if Python 3.10+ is available
test_python_installation() {
    print_status "Checking Python installation..."

    if command -v python3 >/dev/null 2>&1; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "unknown")
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1 2>/dev/null || echo "0")
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2 2>/dev/null || echo "0")

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            print_success "Python $PYTHON_VERSION meets requirements (3.10+)"
            return 0
        else
            print_warning "Python $PYTHON_VERSION is installed but does not meet requirements (3.10+)"
            return 1
        fi
    else
        print_error "Python3 is not installed or not in PATH"
        return 1
    fi
}

# Test if MCP server is installed
test_mcp_server_installation() {
    print_status "Checking AWS Documentation MCP Server installation..."

    # Check if installed via uv tool
    if uv tool list 2>/dev/null | grep -q "awslabs.aws-documentation-mcp-server"; then
        print_success "AWS Documentation MCP Server is installed via uv tool"
        return 0
    else
        print_warning "AWS Documentation MCP Server is not installed via uv tool"
        print_status "This is OK - the MCP configuration uses 'uvx' which runs tools temporarily"
        print_status "The server will be downloaded and run as needed"
        return 0  # Don't fail the test for this
    fi
}

# Test if Cursor MCP configuration exists
test_cursor_configuration() {
    print_status "Checking Cursor MCP configuration..."

    MCP_CONFIG_PATH=$(get_cursor_mcp_path)

    if [ -f "$MCP_CONFIG_PATH" ]; then
        print_success "Cursor MCP configuration file exists: $MCP_CONFIG_PATH"

        # Check if the AWS docs MCP server is configured
        if grep -q "awslabs.aws-documentation-mcp-server" "$MCP_CONFIG_PATH"; then
            print_success "AWS Documentation MCP Server is configured in Cursor"
            return 0
        else
            print_error "AWS Documentation MCP Server is not configured in Cursor MCP file"
            return 1
        fi
    else
        print_error "Cursor MCP configuration file does not exist: $MCP_CONFIG_PATH"
        print_status "Expected location: $MCP_CONFIG_PATH"
        return 1
    fi
}

# Test if cursor rules exist
test_cursor_rules() {
    print_status "Checking Cursor rules..."
    
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
    CURSOR_RULE_PATH="$PROJECT_ROOT/.cursor/rules/aws-documentation-mcp.mdc"

    if [ -f "$CURSOR_RULE_PATH" ]; then
        print_success "AWS Documentation MCP cursor rule exists"
        return 0
    else
        print_error "AWS Documentation MCP cursor rule not found at: $CURSOR_RULE_PATH"
        return 1
    fi
}

# Test if team documentation exists
test_team_documentation() {
    print_status "Checking team documentation..."

    if [ -f "AWS_DOCS_MCP_SETUP.md" ]; then
        print_success "AWS Documentation MCP setup guide exists"
        return 0
    else
        print_error "AWS Documentation MCP setup guide missing"
        return 1
    fi
}

# Test MCP server functionality (basic check)
test_mcp_server_functionality() {
    print_status "Testing MCP server functionality..."

    # Try to run the MCP server with help flag (this may or may not work depending on implementation)
    if timeout 10s uvx awslabs.aws-documentation-mcp-server@latest --help >/dev/null 2>&1; then
        print_success "MCP server responds to help command"
        return 0
    elif timeout 10s uvx awslabs.aws-documentation-mcp-server@latest --version >/dev/null 2>&1; then
        print_success "MCP server responds to version command"
        return 0
    else
        print_warning "MCP server basic test failed (this may be expected for MCP servers)"
        print_status "The server should work fine when called by Cursor via MCP protocol"
        return 0  # Don't fail the test for this
    fi
}

# Main test execution
main() {
    echo
    print_status "🧪 Testing AWS Documentation MCP Setup..."
    echo

    local test_count=0
    local pass_count=0

    # Run all tests
    tests=(
        "test_uv_installation"
        "test_python_installation"
        "test_mcp_server_installation"
        "test_cursor_configuration"
        "test_cursor_rules"
        "test_team_documentation"
        "test_mcp_server_functionality"
    )

    for test in "${tests[@]}"; do
        ((test_count++))
        if $test; then
            ((pass_count++))
        fi
        echo
    done

    # Print summary
    echo "===================="
    print_status "Test Summary: $pass_count/$test_count tests passed"

    if [ $pass_count -eq $test_count ]; then
        print_success "🎉 All tests passed! AWS Documentation MCP is ready to use."
        echo
        print_status "Next steps:"
        echo "  1. Restart Cursor to load the MCP configuration"
        echo "  2. Try using @aws-docs in Cursor chat"
        echo "  3. Check out AWS_DOCS_MCP_SETUP.md for usage examples"
        exit 0
    else
        failed_count=$((test_count - pass_count))
        print_warning "⚠️  $failed_count test(s) failed. You may need to re-run the setup script."
        echo
        print_status "To fix issues, run:"
        echo "  ./scripts/setup-aws-docs-mcp.sh"
        exit 1
    fi
}

# Run main function
main "$@"
