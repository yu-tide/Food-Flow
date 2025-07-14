"use client";

import { useEffect, useState } from "react";

export function useGreeting(): string {
  const [greeting, setGreeting] = useState("早上好");

  useEffect(() => {
    const update = () => {
      const h = new Date().getHours();
      if (h >= 5 && h < 12) setGreeting("早上好");
      else if (h >= 12 && h < 14) setGreeting("中午好");
      else if (h >= 14 && h < 18) setGreeting("下午好");
      else if (h >= 18 && h < 23) setGreeting("晚上好");
      else setGreeting("夜深了");
    };
    update();
    const timer = setInterval(update, 60000);
    return () => clearInterval(timer);
  }, []);

  return greeting;
}
