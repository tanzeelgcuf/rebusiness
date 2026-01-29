import logging
from typing import List, Dict, Any
from pathlib import Path
import yaml

logger = logging.getLogger(__name__)

# Load config
CONFIG_PATH = Path(__file__).parent / "config.yaml"
if CONFIG_PATH.exists():
    with open(CONFIG_PATH, "r") as f:
        CONFIG = yaml.safe_load(f)

class VendorSelector:
    """
    Selects the best vendors from search results based on criteria.
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG
        self.selection_config = self.config.get("vendor_selection", {})
        
    def select_top_vendors(self, vendors: List[Dict[str, Any]], product_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Rank and select top vendors matching criteria.
        
        Args:
            vendors: List of raw vendor dictionaries from search
            product_data: Product info (could be used for more advanced matching later)
            
        Returns:
            List of selected vendor dictionaries
        """
        if not vendors:
            return []
            
        max_vendors = self.selection_config.get("max_vendors_per_product", 5)
        min_rating = self.selection_config.get("min_rating", 0.0)
        require_verification = self.selection_config.get("require_verification", False)
        
        scored_vendors = []
        
        for vendor in vendors:
            # 1. Filter by hard requirements
            if require_verification and not vendor.get("verified"):
                logger.debug(f"Skipping {vendor['name']} - not verified")
                continue
                
            if vendor.get("rating", 0) < min_rating and vendor.get("rating", 0) > 0:
                # Note: keeping vendors with 0 rating (unknown) unless strict strict enforcement
                # Adjust logic based on preference. Here we skip known bad ratings.
                logger.debug(f"Skipping {vendor['name']} - rating {vendor['rating']} < {min_rating}")
                continue
                
            # 2. Calculate Score
            score = self._calculate_score(vendor)
            vendor["selection_score"] = score
            scored_vendors.append(vendor)
            
        # 3. Sort by score (descending)
        scored_vendors.sort(key=lambda x: x["selection_score"], reverse=True)
        
        # 4. Select top N
        selected = scored_vendors[:max_vendors]
        
        logger.info(f"Selected {len(selected)} vendors from {len(vendors)} candidates")
        return selected
        
    def _calculate_score(self, vendor: Dict[str, Any]) -> float:
        """Calculate a selection score (0-100) for a vendor."""
        score = 50.0 # Base score
        
        # Rating boost (up to +30)
        rating = vendor.get("rating", 0)
        if rating > 0:
            score += (rating / 5.0) * 30
            
        # Verification boost (+20)
        if vendor.get("verified"):
            score += 20
            
        # Rank penalty (lower rank in search results is worse)
        # Assuming rank 1 is best. Penalty: -1 per position
        rank_penalty = min(20, vendor.get("rank", 100))
        score -= rank_penalty
        
        return max(0.0, score)

if __name__ == "__main__":
    # Test
    selector = VendorSelector()
    test_vendors = [
        {"name": "Good Vendor", "rating": 4.5, "verified": True, "rank": 1},
        {"name": "Okay Vendor", "rating": 3.0, "verified": False, "rank": 2},
        {"name": "Bad Vendor", "rating": 2.0, "verified": False, "rank": 3},
        {"name": "New Vendor", "rating": 0.0, "verified": True, "rank": 4},
    ]
    selected = selector.select_top_vendors(test_vendors, {})
    import json
    print(json.dumps(selected, indent=2))
