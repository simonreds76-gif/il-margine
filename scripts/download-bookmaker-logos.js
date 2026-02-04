const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

// Bookmaker logo URLs (using CDN sources or official media kits)
const bookmakerLogos = {
  'bet365.png': 'https://logos-world.net/wp-content/uploads/2020/06/Bet365-Logo.png',
  'betfair.png': 'https://logos-world.net/wp-content/uploads/2020/06/Betfair-Logo.png',
  'paddypower.png': 'https://logos-world.net/wp-content/uploads/2020/06/Paddy-Power-Logo.png',
  'williamhill.png': 'https://logos-world.net/wp-content/uploads/2020/06/William-Hill-Logo.png',
  'ladbrokes.png': 'https://logos-world.net/wp-content/uploads/2020/06/Ladbrokes-Logo.png',
  'coral.png': 'https://logos-world.net/wp-content/uploads/2020/06/Coral-Logo.png',
  'skybet.png': 'https://logos-world.net/wp-content/uploads/2020/06/Sky-Bet-Logo.png',
  'unibet.png': 'https://logos-world.net/wp-content/uploads/2020/06/Unibet-Logo.png',
  'betway.png': 'https://logos-world.net/wp-content/uploads/2020/06/Betway-Logo.png',
  '888sport.png': 'https://logos-world.net/wp-content/uploads/2020/06/888sport-Logo.png',
  'betvictor.png': 'https://logos-world.net/wp-content/uploads/2020/06/BetVictor-Logo.png',
  'betfred.png': 'https://logos-world.net/wp-content/uploads/2020/06/Betfred-Logo.png',
  'pinnacle.png': 'https://logos-world.net/wp-content/uploads/2020/06/Pinnacle-Logo.png',
  'betmgm.png': 'https://logos-world.net/wp-content/uploads/2020/06/BetMGM-Logo.png',
};

const outputDir = path.join(__dirname, '..', 'public', 'bookmakers');

// Create directory if it doesn't exist
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

function downloadFile(url, filepath) {
  return new Promise((resolve, reject) => {
    const protocol = url.startsWith('https') ? https : http;
    
    protocol.get(url, (response) => {
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
    }).on('error', reject);
  });
}

async function downloadAllLogos() {
  console.log('Downloading bookmaker logos...\n');
  
  const promises = Object.entries(bookmakerLogos).map(async ([filename, url]) => {
    const filepath = path.join(outputDir, filename);
    try {
      await downloadFile(url, filepath);
    } catch (error) {
      console.error(`✗ Failed to download ${filename}: ${error.message}`);
    }
  });
  
  await Promise.all(promises);
  console.log('\n✓ All logos downloaded!');
  console.log(`\nLogos saved to: ${outputDir}`);
  console.log('\nNote: Some logos may need manual adjustment. Check the files and replace any that look incorrect.');
}

downloadAllLogos().catch(console.error);
