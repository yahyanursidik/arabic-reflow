import { test, expect } from "@playwright/test";
import path from "node:path";

test("browser-injected html attributes do not interrupt hydration", async ({ page }) => {
  const hydrationErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && /hydrat|server rendered HTML/i.test(message.text())) {
      hydrationErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => hydrationErrors.push(error.message));
  await page.addInitScript(() => {
    const inject = () => {
      if (!document.documentElement) return false;
      document.documentElement.setAttribute("webcrx", "");
      document.documentElement.setAttribute("webcrx-bridged", "");
      return true;
    };
    if (!inject()) {
      const observer = new MutationObserver(() => {
        if (inject()) observer.disconnect();
      });
      observer.observe(document, { childList: true });
    }
  });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("webcrx", "");
  await expect(page.locator("html")).toHaveAttribute("webcrx-bridged", "");
  // A state change confirms client hydration finished before checking console errors.
  await page.getByLabel("Pilih dokumen PDF").setInputFiles(
    path.resolve(__dirname, "../../../tests/fixtures/mixed-id-ar.pdf"),
  );
  await expect(page.getByRole("button", { name: "Unggah & lanjutkan" })).toBeEnabled();
  expect(hydrationErrors).toEqual([]);
});
