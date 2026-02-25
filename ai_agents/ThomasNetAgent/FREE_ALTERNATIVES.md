# Free Alternatives to Paid Proxies

## Option 1: Use Tor Network (Free) ⭐ RECOMMENDED

Tor provides free, anonymous browsing through multiple relay nodes.

### Setup:
```bash
# Install Tor
brew install tor

# Start Tor service
brew services start tor
```

### Configure in `.env`:
```bash
# Tor runs on localhost:9050 by default (SOCKS5)
THOMASNET_PROXY=socks5://127.0.0.1:9050
```

**Pros**: 
- Completely free
- Changes IP automatically
- Good anonymity

**Cons**: 
- Slower than paid proxies
- Some sites block Tor exit nodes
- May need to rotate circuits manually

---

## Option 2: Free Proxy Lists

Use free public proxies (less reliable but free).

### Websites for Free Proxies:
- https://www.freeproxy.world
- https://free-proxy-list.net
- https://www.proxy-list.download/HTTPS

### Example `.env` configuration:
```bash
# Example free proxy (changes frequently)
THOMASNET_PROXY=http://proxy-ip:port
```

**Pros**: 
- Free
- Many options available

**Cons**: 
- Very unreliable (proxies die frequently)
- Slow
- Security risk (don't use for sensitive data)
- Need to rotate often

---

## Option 3: Use Your Phone's Hotspot

Simple and effective for bypassing IP blocks.

### Steps:
1. Enable hotspot on your phone
2. Connect your computer to the hotspot
3. Run the ThomasNet agent
4. Your IP will be your mobile carrier's IP

**Pros**: 
- Free (uses your mobile data)
- Different IP from your home/office
- Reliable

**Cons**: 
- Uses mobile data
- May be slower
- Not automated (manual connection)

---

## Option 4: Use a Free VPN

Several VPNs offer free tiers with limited bandwidth.

### Free VPN Options:
- **ProtonVPN**: Unlimited bandwidth, free tier
- **Windscribe**: 10GB/month free
- **TunnelBear**: 500MB/month free

### Setup:
1. Install VPN client
2. Connect to VPN
3. Run ThomasNet agent (no proxy config needed)

**Pros**: 
- Easy to use
- Changes your IP
- More reliable than free proxies

**Cons**: 
- Limited bandwidth
- May be slow
- Still might get blocked if many users use same VPN

---

## Option 5: Run in Non-Headless Mode with Manual Login

Skip automation for login, do it manually.

### Update `config.yaml`:
```yaml
headless: false  # Show browser window
```

### Process:
1. Browser opens (visible)
2. You manually log in to ThomasNet
3. Solve any captchas manually
4. Agent continues automation after login

**Pros**: 
- No proxy needed
- Works with your real IP if not completely blocked
- Can solve captchas manually

**Cons**: 
- Not fully automated
- Requires manual intervention
- Doesn't help if IP is hard-blocked

---

## Option 6: Use AWS/GCP Free Tier

Run the agent from a cloud VM with a different IP.

### AWS Free Tier:
- 750 hours/month free for 12 months
- Different IP address
- Can run 24/7

### Setup:
```bash
# Launch EC2 instance (t2.micro)
# SSH into instance
# Clone your repo
# Run the agent
```

**Pros**: 
- Free for 12 months
- Different IP
- Can run continuously

**Cons**: 
- Requires AWS account
- Setup complexity
- Limited to 12 months free

---

## Option 7: Rotate User Agents + Delays

Sometimes just changing user agent and adding delays works.

### Update `config.yaml`:
```yaml
delay_between_searches: 10  # Increase from 3 to 10 seconds
```

### Rotate User Agents:
We can add user agent rotation to make requests look more natural.

**Pros**: 
- Free
- Simple
- May work for soft blocks

**Cons**: 
- Doesn't change IP
- May not work for hard IP blocks

---

## RECOMMENDED APPROACH: Tor + Non-Headless Mode

**Best free solution**:

1. **Install Tor**:
```bash
brew install tor
brew services start tor
```

2. **Update `.env`**:
```bash
THOMASNET_PROXY=socks5://127.0.0.1:9050
```

3. **Update `config.yaml`**:
```yaml
headless: false  # So you can manually solve captchas
```

4. **Run test**:
```bash
python test_thomasnet_auth.py
```

This gives you:
- ✅ Free proxy (Tor)
- ✅ Different IP
- ✅ Ability to manually solve captchas
- ✅ No monthly fees

---

## Quick Start: Try Tor Now

```bash
# Install Tor
brew install tor

# Start Tor
brew services start tor

# Verify Tor is running
curl --socks5 127.0.0.1:9050 https://check.torproject.org/api/ip

# Update .env
echo "THOMASNET_PROXY=socks5://127.0.0.1:9050" >> .env

# Test
python test_thomasnet_auth.py
```

Let me know which option you'd like to try!
