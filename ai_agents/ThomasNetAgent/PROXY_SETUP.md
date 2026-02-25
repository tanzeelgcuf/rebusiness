# Smart Proxy Setup for ThomasNet Agent

## Why You Need a Proxy

If your IP address is blocked by ThomasNet (common with automation), you'll need to use residential proxies to:
- Bypass IP blocks
- Maintain consistent sessions with sticky IPs
- Avoid rate limiting

## Recommended: Smart Proxy

Smart Proxy offers residential proxies with sticky sessions (10-30 min same IP).

### Setup Steps

1. **Sign up for Smart Proxy**
   - Go to https://smartproxy.com
   - Choose "Residential Proxies" plan
   - Minimum recommended: 2GB plan (~$14/month)

2. **Get Your Credentials**
   - Login to Smart Proxy dashboard
   - Navigate to "Residential Proxies" → "Endpoint Generator"
   - Select:
     - **Location**: United States (or your target region)
     - **Session Type**: Sticky
     - **Session Duration**: 10 minutes (or 30 minutes)
   - Copy the generated proxy URL

3. **Configure the Proxy**
   
   The proxy URL format from Smart Proxy will look like:
   ```
   http://user-USERNAME-session-RANDOM123:PASSWORD@gate.smartproxy.com:7000
   ```

   Add this to your `.env` file:
   ```bash
   THOMASNET_PROXY=http://user-USERNAME-session-RANDOM123:PASSWORD@gate.smartproxy.com:7000
   ```

4. **Test the Connection**
   ```bash
   python test_thomasnet_auth.py
   ```

## Alternative: Other Proxy Providers

If you prefer other providers:

### Bright Data (formerly Luminati)
- More expensive but very reliable
- Format: `http://customer-USERNAME-session-RANDOM:PASSWORD@brd.superproxy.io:22225`

### Oxylabs
- Good for enterprise use
- Format: `http://customer-USERNAME:PASSWORD@pr.oxylabs.io:7777`

### IPRoyal
- Budget-friendly option
- Format: `http://USERNAME:PASSWORD@geo.iproyal.com:12321`

## Sticky Sessions Explained

Sticky sessions keep you on the same IP address for a set duration (e.g., 10-30 minutes). This is crucial for:
- Maintaining login sessions
- Avoiding "suspicious activity" flags
- Completing multi-step workflows

The `session-RANDOM123` part in the proxy URL creates a unique session ID. Change this ID to rotate to a new IP.

## Troubleshooting

### Proxy Connection Failed
- Verify credentials are correct
- Check your Smart Proxy dashboard for active subscription
- Ensure you have remaining bandwidth

### Still Getting Blocked
- Try changing the session ID to get a new IP
- Increase session duration to 30 minutes
- Add delays between requests (already configured in `config.yaml`)

### Slow Performance
- Choose a closer geographic location
- Upgrade to a higher bandwidth plan
- Use datacenter proxies for non-login operations (faster but more detectable)

## Cost Estimation

For moderate ThomasNet automation (100-200 searches/day):
- **Smart Proxy 2GB**: ~$14/month (recommended for testing)
- **Smart Proxy 10GB**: ~$50/month (recommended for production)
- **Bright Data**: ~$500/month (enterprise-grade)

## No Proxy Option

If you don't want to use proxies:
1. Leave `THOMASNET_PROXY` empty in `.env`
2. Use a VPN to change your IP manually
3. Contact ThomasNet support to unblock your IP
4. Run the agent less frequently to avoid rate limits
