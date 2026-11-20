import { expect, test } from '@playwright/test';

const password = process.env.AGRINEXA_UAT_BROWSER_PASSWORD;
const accounts = [
  ['admin', process.env.AGRINEXA_UAT_ADMIN_EMAIL],
  ['gis_operator', process.env.AGRINEXA_UAT_GIS_EMAIL],
  ['ml_team', process.env.AGRINEXA_UAT_ML_EMAIL],
];

test.beforeAll(() => {
  if (!password || accounts.some(([, email]) => !email)) {
    throw new Error('Ephemeral live Agent UAT credentials are required');
  }
});

async function signIn(page, email) {
  await page.getByLabel('Account email').fill(email);
  await page.getByLabel('Account password').fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.locator('.auth-panel')).toContainText('Signed in:');
}

test('real FastAPI Agent Metadata is available to governance roles', async ({ page }) => {
  const pageErrors = [];
  const failedRequests = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('requestfailed', request => failedRequests.push(request.url()));

  for (const [role, email] of accounts) {
    await page.goto('/');
    await signIn(page, email);
    await page.getByRole('navigation', { name: 'Main navigation' })
      .getByRole('button', { name: 'AI Agents', exact: true }).click();

    await expect(page.getByRole('heading', { name: 'Agent metadata' })).toBeVisible();
    await expect(page.locator('.agent-card')).toHaveCount(8);
    await expect(page.locator('.agent-summary')).toContainText('Total agents8');
    await expect(page.locator('.agent-summary')).toContainText('Configured enabled2');
    await expect(page.locator('.agent-summary')).toContainText('Configured disabled6');
    await expect(page.locator('.agent-summary')).toContainText('Dedicated routes8');

    const learningWorkspace = page.getByRole('heading', { name: 'Learning and feedback review' });
    if (role === 'gis_operator') await expect(learningWorkspace).toHaveCount(0);
    else await expect(learningWorkspace).toBeVisible();

    await page.getByRole('button', { name: 'Sign out' }).click();
  }

  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});

test('real FastAPI denies Farmer access to Agent Metadata navigation', async ({ page }) => {
  const farmerEmail = process.env.AGRINEXA_UAT_FARMER_EMAIL;
  if (!farmerEmail) throw new Error('Ephemeral Farmer UAT account is required');
  await page.goto('/');
  await signIn(page, farmerEmail);
  await expect(page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'AI Agents', exact: true })).toHaveCount(0);
});
