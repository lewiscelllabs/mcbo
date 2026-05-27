#!/bin/bash
# Script to download external OBO ontologies required by MCBO
# Run this from your-repo/ directory: bash scripts/download_imports.sh

set -e  # Exit on error

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== MCBO Ontology Import Downloader ===${NC}"
echo ""

# Create ontology/imports directory if it doesn't exist
if [ ! -d "ontology/imports" ]; then
    echo -e "${YELLOW}Creating ontology/imports/ directory...${NC}"
    mkdir -p ontology/imports
fi

cd ontology/imports

# Define ontologies to download
declare -A ONTOLOGIES=(
    ["go.owl"]="http://purl.obolibrary.org/obo/go.owl"
    ["ro.owl"]="http://purl.obolibrary.org/obo/ro.owl"
    ["so.owl"]="http://purl.obolibrary.org/obo/so.owl"
    ["iao.owl"]="http://purl.obolibrary.org/obo/iao.owl"
    ["uo.owl"]="http://purl.obolibrary.org/obo/uo.owl"
)

# Download each ontology
for filename in "${!ONTOLOGIES[@]}"; do
    url="${ONTOLOGIES[$filename]}"
    
    if [ -f "$filename" ]; then
        echo -e "${YELLOW}⚠ $filename already exists. Skipping...${NC}"
    else
        echo -e "${GREEN}⬇ Downloading $filename...${NC}"
        if curl -L -f -o "$filename" "$url"; then
            echo -e "${GREEN}✓ Successfully downloaded $filename${NC}"
        else
            echo -e "${RED}✗ Failed to download $filename from $url${NC}"
            exit 1
        fi
    fi
    echo ""
done

cd ..

echo -e "${GREEN}=== Download Complete ===${NC}"
echo ""
echo "Downloaded ontologies:"
ls -lh ontology/imports/*.owl
echo ""
echo -e "${GREEN}✓ All ontology/imports ready! Run the test with: pytest python/tests/test_imports.py${NC}"
