import type { Config } from "tailwindcss";
// 把 require 换成标准的 import 语法
import tailwindcssAnimate from "tailwindcss-animate";

const config: Config = {
  // 保留你原本的配置
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  // 使用导入的插件
  plugins: [tailwindcssAnimate],
};

export default config;