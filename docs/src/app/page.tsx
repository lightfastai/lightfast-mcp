import React from "react";
import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <h1 className="text-4xl font-bold mb-8">Lightfast MCP Documentation</h1>
      <p className="text-xl mb-8">
        Welcome to the documentation for Lightfast MCP.
      </p>
      <Link
        href="/docs"
        className="px-6 py-3 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors"
      >
        Go to Documentation
      </Link>
    </main>
  );
}
