"use client";
import Image from "next/image";
import Gallery from "./gallery";
import Contact from "./contact";
import About from "./about";
import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function Home() {
  const [page, setPage] = useState(0);

  const pageVariants = {
    initial: { opacity: 0, x: 50 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -50 },
  };
  return (
    <div className=" max-w-full mx-auto dark:text-white text-center mt-10 sm:mt-20 md:mt-20 lg:mt-20">
      <div className=" text-lg space-x-3"><a>Viktor</a><a>Lundin</a></div>
      <nav className=" flex justify-center mt-6 space-x-8 pb-5">
        <button onClick={() => setPage(0)} className={`text-lg dark:text-white underline-offset-8 hover:underline ${page === 0 && "underline"}`}>
          Gallery
        </button>
        <button onClick={() => setPage(1)} className={`text-lg dark:text-white underline-offset-8 hover:underline ${page === 1 && "underline"}`}>
          About
        </button>
        <button onClick={() => setPage(2)} className={`text-lg dark:text-white underline-offset-8 hover:underline ${page === 2 && "underline"}`}>
          Contact
        </button>
      </nav>
    <div className=" relative overflow-hidden min-h-[400px]">
      {page === 0 && <motion.div
            key="gallery"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.5 }}
          >
            <Gallery />
          </motion.div>}
      {page === 1 && <motion.div
            key="about"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.5 }}
          >
            <About />
          </motion.div>}
          {page === 2 && <motion.div
            key="contact"
            variants={pageVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            transition={{ duration: 0.5 }}
          >
            <Contact />
          </motion.div>}
        
      </div>
    </div>
);
}
