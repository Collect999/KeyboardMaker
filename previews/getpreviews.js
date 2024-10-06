const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

// Load the kvks_index.json file to get keyboard IDs
const kvksIndex = JSON.parse(fs.readFileSync('../kvks_index.json', 'utf8'));
const keyboardIds = Object.keys(kvksIndex);

// Function to sleep for rate limiting
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Create the previews directory if it doesn't exist
const previewsDir = './previews';
if (!fs.existsSync(previewsDir)) {
    fs.mkdirSync(previewsDir);
}

(async () => {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    for (let i = 0; i < keyboardIds.length; i++) {
        const keyboardId = keyboardIds[i];
        const url = `https://keymanweb.com/#ur,${keyboardId}`;

        try {
            console.log(`Processing: ${keyboardId}`);

            // Navigate to the Keyman web page for the current keyboard
            await page.goto(url, { waitUntil: 'networkidle2' });

            // Wait for the text area to be available, then click/focus it to show the keyboard
            await page.waitForSelector('#message', { timeout: 10000 });
            await page.click('#message'); // Simulates clicking the text area

            // Wait for the on-screen keyboard to load
            const keyboardSelector = `.desktop.kmw-osk-inner-frame.kmw-keyboard-${keyboardId.toLowerCase()}`;
            await page.waitForSelector(keyboardSelector, { timeout: 10000 });

            // Capture the on-screen keyboard as an image
            const element = await page.$(keyboardSelector);

            if (element) {
                // Construct the full path for the screenshot
                const screenshotPath = path.join(previewsDir, `${keyboardId}.png`);
                await element.screenshot({ path: screenshotPath });
                console.log(`Screenshot taken for ${keyboardId}`);
            } else {
                console.log(`No keyboard found for ${keyboardId}`);
            }

        } catch (error) {
            console.error(`Error processing ${keyboardId}:`, error);
        }

        // Rate limiting: wait for 5 seconds before processing the next keyboard
        await sleep(5000); // 5000 milliseconds = 5 seconds
    }

    await browser.close();
})();