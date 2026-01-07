# Deploying to Render.com (FREE)

Complete guide to deploy your PDF Processor app to Render's free tier.

## Prerequisites

1. GitHub account
2. Your code pushed to GitHub
3. Render.com account (free)

## Step-by-Step Deployment

### 1. Push Code to GitHub

```bash
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

### 2. Sign Up for Render

1. Go to https://render.com
2. Sign up with GitHub (easiest option)

### 3. Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Select your **pdf-processor-tool** repo

### 4. Configure Service

Render will auto-detect the `render.yaml` configuration file. If not:

**Manual Configuration:**
- **Name**: `pdf-processor` (or any name you like)
- **Region**: Choose closest to you
- **Branch**: `main`
- **Runtime**: `Python 3`
- **Build Command**:
  ```bash
  pip install -r requirements.txt && cd frontend && npm install && npm run build
  ```
- **Start Command**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port $PORT
  ```
- **Plan**: **Free**

### 5. Environment Variables (Optional)

Add these in the Render dashboard under "Environment":

```
DEBUG=false
CORS_ORIGINS=*
```

### 6. Deploy!

1. Click **"Create Web Service"**
2. Render will:
   - Install Python dependencies (including OpenCV)
   - Build your frontend
   - Start the server
3. Wait 5-10 minutes for first deploy

### 7. Access Your App

Once deployed, you'll get a URL like:
```
https://pdf-processor-xxxx.onrender.com
```

Your app is now live! 🎉

## Important Notes

### Free Tier Limitations

- ✅ **Completely FREE**
- ⚠️ **Spins down after 15 minutes** of inactivity
- ⚠️ **First request takes 30-60 seconds** to wake up
- ✅ **750 hours/month** free (enough for continuous use)

### Cold Starts

When your app spins down:
- First visitor waits 30-60s for wake-up
- Subsequent requests are fast
- Perfect for demos and hobby projects

### Keeping App Awake (Optional)

If you want to prevent cold starts:

1. Use a service like **UptimeRobot** (free):
   - Pings your app every 5 minutes
   - Keeps it awake during active hours

2. Or upgrade to Render's paid plan ($7/month):
   - Always-on
   - No cold starts

## Troubleshooting

### Build Fails

**Check logs** in Render dashboard:
1. Go to your service
2. Click "Logs"
3. Look for error messages

**Common issues:**
- Missing dependencies: Add to `requirements.txt`
- Node.js version: Render uses Node 14 by default
- Build timeout: Increase in service settings

### App Crashes

1. Check **Runtime Logs** in Render dashboard
2. Verify environment variables are set
3. Test locally first: `python main.py`

### OpenCV Issues

OpenCV should work fine on Render. If you get errors:
```
ImportError: libGL.so.1
```

Add this to your `render.yaml` under `envVars`:
```yaml
- key: LD_LIBRARY_PATH
  value: /usr/lib/x86_64-linux-gnu
```

## Updating Your App

Render auto-deploys on every push to `main`:

```bash
git add .
git commit -m "Update feature"
git push origin main
```

Render will automatically redeploy! ⚡

## Monitoring

View your app status:
1. Render Dashboard → Your Service
2. See: Metrics, Logs, Events
3. Health checks at `/health`

## Cost

**100% FREE** for hobby projects! 🎉

Only pay if you need:
- Faster response (no cold starts)
- More resources
- Custom domains

---

## Next Steps

1. **Custom Domain**: Add your own domain in Render settings
2. **HTTPS**: Automatic with Render (included free)
3. **Environment Variables**: Add any secrets in dashboard
4. **Monitoring**: Set up UptimeRobot for uptime monitoring

Need help? Check [Render Docs](https://render.com/docs) or ask me!
