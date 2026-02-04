# Domain Setup Guide: ilmargine.bet

## Step 1: Register Domain on Namecheap

1. Go to [namecheap.com](https://www.namecheap.com)
2. Search for `ilmargine.bet` in the search bar
3. Add it to cart and complete purchase (~$20-50/year)
4. After purchase, you'll be taken to your domain management page

## Step 2: Add Domain to Vercel

1. Log into your Vercel account: [vercel.com](https://vercel.com)
2. Go to your **il-margine** project
3. Click **Settings** (top right)
4. Click **Domains** (left sidebar)
5. Click **Add Domain** button
6. Enter: `ilmargine.bet`
7. Click **Add**

Vercel will show you DNS configuration instructions. You'll see something like:

```
Type: A
Name: @
Value: 76.76.21.21

OR

Type: CNAME
Name: @
Value: cname.vercel-dns.com
```

**Keep this page open** - you'll need these values for the next step.

## Step 3: Configure DNS on Namecheap

1. Go back to Namecheap dashboard
2. Click **Domain List** (top menu)
3. Find `ilmargine.bet` and click **Manage**
4. Click **Advanced DNS** tab
5. In the **Host Records** section, you'll see existing records

### Option A: If Vercel gives you an A record:
- Click **Add New Record**
- Type: **A Record**
- Host: **@** (or leave blank)
- Value: **76.76.21.21** (or the IP Vercel provided)
- TTL: **Automatic** (or 30 min)
- Click **Save** (green checkmark)

### Option B: If Vercel gives you a CNAME:
- Click **Add New Record**
- Type: **CNAME Record**
- Host: **@** (or leave blank)
- Value: **cname.vercel-dns.com** (or what Vercel provided)
- TTL: **Automatic**
- Click **Save**

### Important Notes:
- If there's already an A record for `@`, **delete it first** before adding the new one
- You can only have ONE A record or ONE CNAME for `@` - not both
- The `@` symbol means "root domain" (ilmargine.bet)

## Step 4: Wait for DNS Propagation

1. Go back to Vercel → Settings → Domains
2. You'll see `ilmargine.bet` with status: **Pending** or **Configuring**
3. DNS propagation takes **15 minutes to 48 hours** (usually 1-2 hours)
4. Vercel will automatically:
   - Detect when DNS is configured correctly
   - Issue SSL certificate (HTTPS)
   - Update status to **Valid**

## Step 5: Verify It's Working

Once Vercel shows status as **Valid**:
1. Visit `https://ilmargine.bet` in your browser
2. Your site should load exactly as it does on the current Vercel domain
3. You'll see a green padlock (HTTPS) - SSL is automatic!

## Troubleshooting

### Domain shows "Pending" for more than 24 hours?
- Double-check DNS records match exactly what Vercel provided
- Make sure you deleted old A/CNAME records
- Try clearing your browser cache
- Check Namecheap DNS is set to "Namecheap BasicDNS" (not Custom DNS)

### Getting SSL errors?
- Wait a bit longer - SSL certificate generation takes 5-10 minutes after DNS is valid
- Vercel handles SSL automatically, no manual setup needed

### Site not loading?
- Verify DNS records are saved correctly in Namecheap
- Check Vercel domain status shows "Valid"
- Try accessing via `http://ilmargine.bet` (should redirect to HTTPS)

## Optional: Keep Old Domain Active

Your current Vercel domain (e.g., `il-margine.vercel.app`) will continue working. You can:
- Keep both domains active (they point to the same site)
- Or remove the old one later if you prefer

## Need Help?

If you get stuck at any step, let me know:
- What step you're on
- What error message you see (if any)
- Screenshot if possible

I'll help troubleshoot!
