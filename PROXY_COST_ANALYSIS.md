# ThomasNet Proxy Cost Analysis

## Client's Ultimate Goal
- **50 RFQs per day** (daily basis)
- Each RFQ goes to **5 vendors** = **250 vendor submissions per day**

## Bandwidth Usage Estimation

### Per Vendor Submission Breakdown

1. **Login to ThomasNet** (once per session)
   - Page load: ~2-3 MB
   - Session reuse: Only needed once per day

2. **Search for vendors** (per product)
   - Search page load: ~1-2 MB
   - Results parsing: Minimal (already loaded)

3. **Visit vendor profile** (per vendor)
   - Profile page load: ~1-2 MB per vendor
   - 5 vendors × 1.5 MB = ~7.5 MB per product

4. **Fill and submit RFQ form** (per vendor)
   - Form page: Already loaded with profile
   - Form submission: ~0.5 MB per vendor
   - 5 vendors × 0.5 MB = ~2.5 MB per product

### Daily Bandwidth Calculation

**Per Product (1 RFQ to 5 vendors):**
- Login (shared): 2.5 MB ÷ 50 products = 0.05 MB
- Search: 1.5 MB
- Vendor profiles: 7.5 MB
- Form submissions: 2.5 MB
- **Total per product: ~11.5 MB**

**For 50 Products/Day:**
- 50 products × 11.5 MB = **575 MB per day**
- **≈ 0.58 GB per day**

### Monthly Bandwidth
- 0.58 GB/day × 30 days = **~17.4 GB per month**

---

## Cost Analysis

### Option 1: Residential Proxies ($1.50/GB)
- **Daily cost**: 0.58 GB × $1.50 = **$0.87/day**
- **Monthly cost**: 17.4 GB × $1.50 = **$26.10/month**
- **Annual cost**: $26.10 × 12 = **$313.20/year**

### Option 2: Smart Proxy ($12.50/GB) - NOT RECOMMENDED
- Daily cost: 0.58 GB × $12.50 = $7.25/day
- Monthly cost: 17.4 GB × $12.50 = $217.50/month
- ❌ **Too expensive for this use case**

### Option 3: Free Alternatives (Tor)
- **Cost**: $0
- **Pros**: Free, anonymous
- **Cons**: 
  - Slower speeds (3-5x slower)
  - May be blocked by ThomasNet
  - Less reliable
  - No sticky sessions (IP changes frequently)

---

## Recommended Response to Client

### Cost-Benefit Analysis

**Investment**: ~$26/month for residential proxies

**Benefits**:
1. **Avoid IP blocking** - ThomasNet won't ban your IP
2. **Reliable automation** - Consistent performance
3. **Sticky sessions** - Same IP for 10-30 minutes (better for login persistence)
4. **Professional appearance** - Residential IPs look like real users
5. **Scale safely** - Can handle 50+ RFQs/day without issues

**ROI Calculation**:
- Cost per RFQ: $26 ÷ (50 RFQs/day × 30 days) = **$0.017 per RFQ**
- Cost per vendor submission: $26 ÷ (250 submissions/day × 30 days) = **$0.0035 per submission**

**Time Saved**:
- Manual RFQ submission: ~10 minutes per vendor
- 250 submissions/day × 10 min = **41.7 hours/day** of manual work
- At $20/hour labor cost: **$834/day saved** = **$25,020/month saved**

**Net Savings**: $25,020 - $26 = **$24,994/month**

---

## Alternative: Start with Free Tor, Upgrade if Needed

### Phase 1: Test with Tor (Free)
- Run for 1-2 weeks
- Monitor for IP blocks
- Track success rate
- **Cost**: $0

### Phase 2: Upgrade to Residential Proxies if:
- IP gets blocked
- Success rate < 90%
- Need faster performance
- **Cost**: $26/month

---

## Recommended Proxy Provider

For $1.50/GB residential proxies, consider:

1. **Bright Data** (formerly Luminati)
   - $1.50/GB residential
   - Sticky sessions available
   - High quality IPs

2. **Oxylabs**
   - $1.50/GB residential
   - Good for web scraping
   - Reliable uptime

3. **IPRoyal**
   - $1.40/GB residential
   - Slightly cheaper
   - Good performance

---

## Final Recommendation

**Start with Tor (free)** for initial testing. If you encounter:
- IP blocking
- Captcha challenges increasing
- Success rate dropping

Then **upgrade to residential proxies at $26/month** - which is negligible compared to the time and labor savings.

**Bottom Line**: For 50 RFQs/day, residential proxies cost **less than $1/day** and prevent IP blocking that could shut down your entire operation.
