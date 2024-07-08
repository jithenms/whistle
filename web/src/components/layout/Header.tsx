"use client";
import React, { useEffect, useState } from "react";
import { Button } from "../ui/button";

function Header() {
  const [style, setStyle] = useState("");

  const handleScroll = () => {
    if (window.scrollY > 80) {
      setStyle("backdrop-blur bg-black bg-opacity-30");
    } else {
      setStyle("");
    }
  };

  useEffect(() => {
    window.addEventListener("scroll", handleScroll);
    return () => {
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  return (
    <div className="absolute h-full w-full">
      <div
        className={`px-12 top-0 sticky z-50 flex items-center justify-between py-6 ${style}`}
      >
        <p className="text-2xl font-bold">Whistle</p>
        <Button>Submit a feature request</Button>
      </div>
    </div>
  );
}

export default Header;
