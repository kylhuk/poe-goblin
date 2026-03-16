import path from "node:path";
import frontendConfig from "./frontend/vitest.config.ts";

const frontendRoot = path.resolve(__dirname, "frontend");
const frontendTestConfig = frontendConfig.test ?? {};

export default {
  ...frontendConfig,
  root: frontendRoot,
  test: {
    ...frontendTestConfig,
    root: frontendRoot,
  },
};
