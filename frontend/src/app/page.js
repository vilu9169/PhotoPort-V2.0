"use client";

import React, { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";

import About from "./about";
import Contact from "./contact";
import Gallery from "./gallery";

const pages = [
  { id: "gallery", label: "Gallery" },
  { id: "about", label: "About" },
  { id: "contact", label: "Contact" },
];

const constellationUrl =
  process.env.NEXT_PUBLIC_CONSTELLATION_URL ||
  "https://vilu9169.github.io/PhotoConstellation/";

export default function Home() {
  const [page, setPage] = useState("gallery");

  return (
    <main className="site-shell">
      <header className="site-header">
        <button
          type="button"
          className="site-mark"
          onClick={() => setPage("gallery")}
          aria-label="Viktor Lundin, open gallery"
        >
          <span>Viktor Lundin</span>
          <small>Photography</small>
        </button>

        <nav className="site-nav" aria-label="Main navigation">
          {pages.map((item) => (
            <button
              type="button"
              key={item.id}
              onClick={() => setPage(item.id)}
              className={page === item.id ? "is-active" : ""}
              aria-current={page === item.id ? "page" : undefined}
            >
              {item.label}
            </button>
          ))}
          <a
            className="site-nav__external"
            href={constellationUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open Photo Constellation in a new tab"
          >
            Constellation <span aria-hidden="true">↗</span>
          </a>
        </nav>
      </header>

      <AnimatePresence mode="wait">
        <motion.div
          key={page}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
        >
          {page === "gallery" && <Gallery />}
          {page === "about" && <About />}
          {page === "contact" && <Contact />}
        </motion.div>
      </AnimatePresence>
    </main>
  );
}
