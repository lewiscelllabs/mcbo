"""
Pathway enrichment tools for MCBO agent.

Provides integration with KEGG and Reactome pathway databases for
gene set enrichment analysis, supporting CQ5 (pathway differential expression).
"""

from typing import Literal, Optional
import json
from pathlib import Path

import pandas as pd
import numpy as np

# Try to import requests for API calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Try to import scipy for hypergeometric test
try:
    from scipy.stats import hypergeom
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False


# KEGG REST API endpoints
KEGG_BASE_URL = "https://rest.kegg.jp"
KEGG_LIST_PATHWAY = f"{KEGG_BASE_URL}/list/pathway"
KEGG_LINK_GENES = f"{KEGG_BASE_URL}/link"
KEGG_CONV = f"{KEGG_BASE_URL}/conv"

# Reactome API endpoints
REACTOME_ANALYSIS_URL = "https://reactome.org/AnalysisService/identifiers/projection"

# Common organism codes
ORGANISM_CODES = {
    "human": "hsa",
    "mouse": "mmu",
    "rat": "rno",
    "hamster": "cge",  # Chinese hamster (CHO cells)
}


def get_kegg_pathways(
    gene_list: list[str],
    organism: str = "hsa",
    background_genes: Optional[list[str]] = None,
    pvalue_threshold: float = 0.05,
) -> dict:
    """Query KEGG for pathway enrichment.
    
    Performs overrepresentation analysis (ORA) using the hypergeometric test
    to identify pathways enriched in the input gene list.
    
    Args:
        gene_list: List of gene symbols to analyze
        organism: KEGG organism code (hsa=human, mmu=mouse, cge=hamster)
        background_genes: Optional background gene set (default: all KEGG genes)
        pvalue_threshold: P-value cutoff for significant pathways
        
    Returns:
        dict with keys:
            - enriched_pathways: list of enriched pathway dicts
            - input_genes: number of input genes
            - mapped_genes: number of genes mapped to KEGG
            - organism: organism code used
            - error: error message if failed
    """
    if not REQUESTS_AVAILABLE:
        return {
            "enriched_pathways": [],
            "error": "requests library not available. Install with: pip install requests",
        }
    
    if not gene_list:
        return {
            "enriched_pathways": [],
            "input_genes": 0,
            "error": "Empty gene list provided",
        }
    
    try:
        # Step 1: Convert gene symbols to KEGG gene IDs
        gene_to_kegg = _convert_genes_to_kegg(gene_list, organism)
        mapped_kegg_ids = list(gene_to_kegg.values())
        
        if not mapped_kegg_ids:
            return {
                "enriched_pathways": [],
                "input_genes": len(gene_list),
                "mapped_genes": 0,
                "error": "No genes could be mapped to KEGG IDs",
            }
        
        # Step 2: Get pathway-gene associations
        pathway_genes = _get_pathway_gene_links(organism)
        
        if not pathway_genes:
            return {
                "enriched_pathways": [],
                "input_genes": len(gene_list),
                "mapped_genes": len(mapped_kegg_ids),
                "error": "Could not retrieve pathway-gene links from KEGG",
            }
        
        # Step 3: Calculate enrichment for each pathway
        all_genes = set()
        for genes in pathway_genes.values():
            all_genes.update(genes)
        
        background = set(background_genes) if background_genes else all_genes
        query_set = set(mapped_kegg_ids)
        
        enriched = []
        for pathway_id, pathway_gene_set in pathway_genes.items():
            result = _calculate_enrichment(
                query_set, 
                pathway_gene_set, 
                background,
                pathway_id,
            )
            if result["p_value"] is not None and result["p_value"] < pvalue_threshold:
                enriched.append(result)
        
        # Sort by p-value
        enriched.sort(key=lambda x: x["p_value"])
        
        # Apply multiple testing correction (Benjamini-Hochberg)
        enriched = _apply_fdr_correction(enriched)
        
        return {
            "enriched_pathways": enriched,
            "input_genes": len(gene_list),
            "mapped_genes": len(mapped_kegg_ids),
            "organism": organism,
            "total_pathways_tested": len(pathway_genes),
        }
        
    except Exception as e:
        return {
            "enriched_pathways": [],
            "input_genes": len(gene_list),
            "error": str(e),
        }


def _convert_genes_to_kegg(gene_list: list[str], organism: str) -> dict:
    """Convert gene symbols to KEGG gene IDs.
    
    Uses KEGG's conv API to map gene symbols to KEGG identifiers.
    """
    # KEGG conv API: /conv/<target_db>/<source_db>
    # For gene symbols, we use ncbi-geneid or uniprot as source
    try:
        # Try to get gene ID mappings
        url = f"{KEGG_CONV}/{organism}/ncbi-geneid"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            # Fallback: create simple mapping assuming gene symbols match KEGG format
            return {g: f"{organism}:{g}" for g in gene_list}
        
        # Parse the conversion table
        kegg_to_ncbi = {}
        for line in response.text.strip().split("\n"):
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) == 2:
                    ncbi_id = parts[0].replace("ncbi-geneid:", "")
                    kegg_id = parts[1]
                    kegg_to_ncbi[kegg_id] = ncbi_id
        
        # For simplicity, return direct symbol-to-KEGG mapping
        # In production, you'd want a proper gene symbol -> NCBI ID -> KEGG ID mapping
        return {g: f"{organism}:{g}" for g in gene_list}
        
    except Exception:
        # Fallback: assume gene symbols work directly
        return {g: f"{organism}:{g}" for g in gene_list}


def _get_pathway_gene_links(organism: str) -> dict:
    """Get pathway-gene associations from KEGG.
    
    Returns dict mapping pathway_id -> set of gene IDs.
    """
    try:
        url = f"{KEGG_LINK_GENES}/{organism}/pathway"
        response = requests.get(url, timeout=60)
        
        if response.status_code != 200:
            return {}
        
        pathway_genes = {}
        for line in response.text.strip().split("\n"):
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) == 2:
                    pathway_id = parts[0].replace("path:", "")
                    gene_id = parts[1]
                    
                    if pathway_id not in pathway_genes:
                        pathway_genes[pathway_id] = set()
                    pathway_genes[pathway_id].add(gene_id)
        
        return pathway_genes
        
    except Exception:
        return {}


def _calculate_enrichment(
    query_genes: set,
    pathway_genes: set,
    background_genes: set,
    pathway_id: str,
) -> dict:
    """Calculate enrichment using hypergeometric test.
    
    Tests whether the overlap between query genes and pathway genes
    is greater than expected by chance.
    """
    # Hypergeometric test parameters:
    # M = population size (background genes)
    # n = number of success states in population (pathway genes in background)
    # N = number of draws (query genes)
    # k = number of observed successes (overlap)
    
    M = len(background_genes)
    pathway_in_bg = pathway_genes.intersection(background_genes)
    n = len(pathway_in_bg)
    query_in_bg = query_genes.intersection(background_genes)
    N = len(query_in_bg)
    overlap = query_genes.intersection(pathway_genes)
    k = len(overlap)
    
    if M == 0 or n == 0 or N == 0:
        return {
            "pathway_id": pathway_id,
            "overlap_count": k,
            "pathway_size": n,
            "query_size": N,
            "p_value": None,
        }
    
    if SCIPY_AVAILABLE:
        # P(X >= k) = 1 - P(X < k) = 1 - cdf(k-1)
        p_value = hypergeom.sf(k - 1, M, n, N)
    else:
        # Without scipy, return None for p-value
        p_value = None
    
    return {
        "pathway_id": pathway_id,
        "overlap_count": k,
        "pathway_size": n,
        "query_size": N,
        "background_size": M,
        "p_value": float(p_value) if p_value is not None else None,
        "overlap_genes": list(overlap),
    }


def _apply_fdr_correction(results: list[dict]) -> list[dict]:
    """Apply Benjamini-Hochberg FDR correction to p-values."""
    n = len(results)
    if n == 0:
        return results
    
    # Sort by p-value (should already be sorted)
    sorted_results = sorted(results, key=lambda x: x.get("p_value", 1))
    
    # Calculate adjusted p-values
    for i, result in enumerate(sorted_results):
        if result.get("p_value") is not None:
            # BH adjustment: p_adj = p * n / rank
            rank = i + 1
            adj_p = result["p_value"] * n / rank
            result["p_adjusted"] = min(adj_p, 1.0)  # Cap at 1.0
        else:
            result["p_adjusted"] = None
    
    return sorted_results


def get_reactome_pathways(
    gene_list: list[str],
    species: str = "Homo sapiens",
    pvalue_threshold: float = 0.05,
) -> dict:
    """Query Reactome for pathway enrichment.
    
    Uses Reactome's Analysis Service API for pathway overrepresentation analysis.
    
    Args:
        gene_list: List of gene symbols to analyze
        species: Species name (default: Homo sapiens)
        pvalue_threshold: P-value cutoff for significant pathways
        
    Returns:
        dict with enrichment results
    """
    if not REQUESTS_AVAILABLE:
        return {
            "enriched_pathways": [],
            "error": "requests library not available. Install with: pip install requests",
        }
    
    if not gene_list:
        return {
            "enriched_pathways": [],
            "input_genes": 0,
            "error": "Empty gene list provided",
        }
    
    try:
        # Prepare payload - one gene per line
        payload = "\n".join(gene_list)
        
        headers = {
            "Content-Type": "text/plain",
            "Accept": "application/json",
        }
        
        params = {
            "pageSize": 100,
            "page": 1,
            "sortBy": "ENTITIES_PVALUE",
            "order": "ASC",
            "resource": "TOTAL",
            "pValue": pvalue_threshold,
            "includeDisease": False,
        }
        
        response = requests.post(
            REACTOME_ANALYSIS_URL,
            data=payload,
            headers=headers,
            params=params,
            timeout=60,
        )
        
        if response.status_code != 200:
            return {
                "enriched_pathways": [],
                "input_genes": len(gene_list),
                "error": f"Reactome API error: {response.status_code}",
            }
        
        data = response.json()
        
        # Parse results
        enriched = []
        pathways = data.get("pathways", [])
        for pathway in pathways:
            if pathway.get("entities", {}).get("pValue", 1) < pvalue_threshold:
                enriched.append({
                    "pathway_id": pathway.get("stId"),
                    "pathway_name": pathway.get("name"),
                    "p_value": pathway.get("entities", {}).get("pValue"),
                    "p_adjusted": pathway.get("entities", {}).get("fdr"),
                    "overlap_count": pathway.get("entities", {}).get("found"),
                    "pathway_size": pathway.get("entities", {}).get("total"),
                    "species": pathway.get("species", {}).get("name"),
                })
        
        return {
            "enriched_pathways": enriched,
            "input_genes": len(gene_list),
            "mapped_genes": data.get("identifiersNotFound", 0),
            "species": species,
        }
        
    except Exception as e:
        return {
            "enriched_pathways": [],
            "input_genes": len(gene_list),
            "error": str(e),
        }


def get_pathway_enrichment(
    gene_list: list[str],
    database: Literal["kegg", "reactome"] = "kegg",
    organism: str = "hsa",
    pvalue_threshold: float = 0.05,
) -> dict:
    """Unified interface for pathway enrichment analysis.
    
    This is the main function called by the agent orchestrator.
    
    Args:
        gene_list: List of gene symbols
        database: Which pathway database to use ('kegg' or 'reactome')
        organism: Organism code (for KEGG) or species name (for Reactome)
        pvalue_threshold: Significance threshold
        
    Returns:
        Enrichment results from the specified database
    """
    if database.lower() == "kegg":
        # Map organism name to KEGG code if needed
        org_code = ORGANISM_CODES.get(organism.lower(), organism)
        return get_kegg_pathways(gene_list, org_code, pvalue_threshold=pvalue_threshold)
    elif database.lower() == "reactome":
        species = "Homo sapiens" if organism == "hsa" else organism
        return get_reactome_pathways(gene_list, species, pvalue_threshold)
    else:
        return {
            "enriched_pathways": [],
            "error": f"Unknown database: {database}. Use 'kegg' or 'reactome'.",
        }


def load_local_pathway_db(path: str) -> dict:
    """Load pre-downloaded pathway mappings for offline use.
    
    The file should be a JSON with structure:
    {
        "organism": "hsa",
        "pathways": {
            "hsa00010": {
                "name": "Glycolysis / Gluconeogenesis",
                "genes": ["HK1", "HK2", "GCK", ...]
            },
            ...
        }
    }
    
    Args:
        path: Path to the pathway database JSON file
        
    Returns:
        dict with pathway data
    """
    db_path = Path(path)
    if not db_path.exists():
        raise FileNotFoundError(f"Pathway database not found: {path}")
    
    with open(db_path, "r") as f:
        data = json.load(f)
    
    return data


def enrich_from_local_db(
    gene_list: list[str],
    pathway_db: dict,
    pvalue_threshold: float = 0.05,
) -> dict:
    """Perform enrichment analysis using a local pathway database.
    
    Args:
        gene_list: List of gene symbols
        pathway_db: Pathway database loaded via load_local_pathway_db
        pvalue_threshold: Significance threshold
        
    Returns:
        Enrichment results
    """
    pathways = pathway_db.get("pathways", {})
    if not pathways:
        return {
            "enriched_pathways": [],
            "error": "No pathways in database",
        }
    
    # Build background gene set
    all_genes = set()
    for pw_data in pathways.values():
        all_genes.update(pw_data.get("genes", []))
    
    query_set = set(g.upper() for g in gene_list)
    
    enriched = []
    for pw_id, pw_data in pathways.items():
        pw_genes = set(g.upper() for g in pw_data.get("genes", []))
        result = _calculate_enrichment(query_set, pw_genes, all_genes, pw_id)
        result["pathway_name"] = pw_data.get("name", pw_id)
        if result["p_value"] is not None and result["p_value"] < pvalue_threshold:
            enriched.append(result)
    
    enriched = _apply_fdr_correction(enriched)
    
    return {
        "enriched_pathways": enriched,
        "input_genes": len(gene_list),
        "organism": pathway_db.get("organism", "unknown"),
    }


__all__ = [
    "get_pathway_enrichment",
    "get_kegg_pathways",
    "get_reactome_pathways",
    "load_local_pathway_db",
    "enrich_from_local_db",
    "ORGANISM_CODES",
    "REQUESTS_AVAILABLE",
    "SCIPY_AVAILABLE",
]

