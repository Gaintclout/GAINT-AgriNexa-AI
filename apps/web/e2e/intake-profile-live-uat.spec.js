import { expect, test } from '@playwright/test';

const password = process.env.AGRINEXA_UAT_BROWSER_PASSWORD;
const operatorEmail = process.env.AGRINEXA_UAT_ADMIN_EMAIL;
const parcelId = '17000000-0000-4000-8000-000000000017';
const farmerId = 'm17-uat-farmer';

test.beforeAll(() => {
  if (!password || !operatorEmail) throw new Error('Ephemeral M17 credentials required');
});

test('authorized browser preview returns parcel profile and commits through real API', async ({ page }) => {
  const pageErrors = [];
  const failedRequests = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('requestfailed', request => failedRequests.push(request.url()));

  await page.goto('/');
  await page.getByLabel('Account email').fill(operatorEmail);
  await page.getByLabel('Account password').fill(password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page.locator('.auth-panel')).toContainText('Signed in: admin');
  await page.getByRole('navigation', { name: 'Main navigation' })
    .getByRole('button', { name: 'AI Agents', exact: true }).click();

  await expect(page.getByRole('heading', { name: 'Intake and Profile' })).toBeVisible();
  await expect(page.getByText('Intake/Profile API is available.')).toBeVisible();
  await page.getByRole('combobox', { name: 'Parcel', exact: true }).selectOption(parcelId);
  await page.getByRole('textbox', { name: 'Crop name', exact: true }).fill('  rice  ');
  await page.getByRole('textbox', { name: 'Season', exact: true }).fill('  kharif  ');

  const responsePromise = page.waitForResponse(response =>
    response.url().endsWith('/api/v1/agents/intake-profile/preview')
    && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Generate profile' }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.intake).toMatchObject({
    farmer_id: farmerId,
    parcel_id: parcelId,
    crop_name: 'rice',
    season: 'kharif',
    status: 'validated',
  });
  expect(body.profile).toMatchObject({
    farmer_id: farmerId,
    parcel_id: parcelId,
    completeness_percent: 100,
    status: 'complete',
  });
  expect(body).toMatchObject({
    village_code: 'M17-UAT-VILLAGE',
    area_hectares: '2.5000',
    data_source: 'parcel_registry',
    persisted: false,
  });

  const result = page.getByRole('region', { name: 'Generated intake profile' });
  await expect(result).toContainText(parcelId);
  await expect(result).toContainText('M17-UAT-VILLAGE');
  await expect(result).toContainText('2.5000');
  await expect(result).toContainText('parcel_registry');
  expect(pageErrors).toEqual([]);
  expect(failedRequests).toEqual([]);
});
