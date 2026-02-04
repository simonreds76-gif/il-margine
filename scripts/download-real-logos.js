const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Direct image URLs from CDNs and official sources
// Using multiple fallback sources for each logo
const bookmakerLogos = {
  'bet365.png': [
    'https://www.bet365.com/favicon.ico',
  ],
  'betfair.png': [
    'https://www.betfair.com/favicon.ico',
  ],
  'paddypower.png': [
    'https://www.paddypower.com/favicon.ico',
    'https://www.paddypower.com/assets/images/logo.png',
  ],
  'williamhill.png': [
    'https://www.williamhill.com/favicon.ico',
    'https://www.williamhill.com/assets/images/logo.png',
  ],
  'ladbrokes.png': [
    'https://www.ladbrokes.com/favicon.ico',
    'https://www.ladbrokes.com/assets/images/logo.png',
  ],
  'coral.png': [
    'https://www.coral.co.uk/favicon.ico',
    'https://www.coral.co.uk/assets/images/logo.png',
  ],
  'skybet.png': [
    'https://www.skybet.com/favicon.ico',
  ],
  'unibet.png': [
    'https://www.unibet.com/favicon.ico',
  ],
  'betway.png': [
    'https://www.betway.com/favicon.ico',
    'https://www.betway.com/assets/images/logo.png',
  ],
  '888sport.png': [
    'https://www.888sport.com/favicon.ico',
    'https://www.888sport.com/assets/images/logo.png',
  ],
  'betvictor.png': [
    'https://www.betvictor.com/favicon.ico',
  ],
  'betfred.png': [
    'https://www.betfred.com/favicon.ico',
    'https://www.betfred.com/assets/images/logo.png',
  ],
  'pinnacle.png': [
    'https://www.pinnacle.com/favicon.ico',
    'https://www.pinnacle.com/assets/images/logo.png',
  ],
  'betmgm.png': [
    'https://www.betmgm.com/favicon.ico',
    'https://www.betmgm.com/assets/images/logo.png',
  ],
};

const outputDir = path.join(__dirname, '..', 'public', 'bookmakers');

// Create directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

function downloadFile(url, filepath) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https') ? https : http;
    
    const request = protocol.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
      }
    }, (response) => {
      if (response.statusCode === 301 || response.statusCode === 302) {
        // Handle redirects
        return downloadFile(response.headers.location, filepath)
          .then(resolve)
          .catch(reject);
      }
      
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }
      
      const fileStream = fs.createWriteStream(filepath);
      response.pipe(fileStream);
      
      fileStream.on('finish', () => {
        fileStream.close();
        console.log(`✓ Downloaded: ${path.basename(filepath)}`);
        resolve();
      });
      
      fileStream.on('error', (err) => {
        fs.unlink(filepath, () => {});
        reject(err);
      });
    });
    
    request.on('error', reject);
    request.setTimeout(10000, () => {
      request.destroy();
      reject(new Error('Request timeout'));
    });
  });
}

async function downloadLogo(filename, urls) {
  for (const url of urls) {
    try {
      const filepath = path.join(outputDir, filename);
      await downloadFile(url, filepath);
      return true; // Success
    } catch (error) {
      // Try next URL
      continue;
    }
  }
  return false; // All URLs failed
}

async function downloadAllLogos() {
  console.log('Downloading bookmaker logos from official sources...\n');
  
  const results = await Promise.allSettled(
    Object.entries(bookmakerLogos).map(async ([filename, urls]) => {
      const success = await downloadLogo(filename, urls);
      if (!success) {
        console.error(`✗ Failed to download ${filename} from all sources`);
      }
      return { filename, success };
    })
  );
  
  const successful = results.filter(r => r.status === 'fulfilled' && r.value.success).length;
  const failed = results.length - successful;
  
  console.log(`\n✓ Downloaded ${successful} logos`);
  if (failed > 0) {
    console.log(`✗ Failed to download ${failed} logos`);
    console.log('\nNote: Some logos may need to be downloaded manually from:');
    console.log('- Official bookmaker affiliate portals');
    console.log('- Bookmaker press/media sections');
    console.log('- Logo databases (logos-world.net, brandfetch.com)');
  }
  console.log(`\nLogos saved to: ${outputDir}`);
}

downloadAllLogos().catch(console.error);
