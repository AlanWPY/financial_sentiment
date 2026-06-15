import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from crawler.enhanced_collect import enhanced_cninfo, enhanced_eastmoney_sections, enhanced_guba


if __name__ == "__main__":
    total = 0
    total += enhanced_guba(5)
    total += enhanced_cninfo(12)
    total += enhanced_eastmoney_sections()
    print(total)
