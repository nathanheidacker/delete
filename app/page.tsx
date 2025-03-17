"use client";

import { useState, useRef } from "react";
import { Editor } from "@/components/Editor";
import { SubmitPdf, type SubmitPdfHandle } from "@/components/SubmitPdf";

export default function Home() {
    const [content, setContent] = useState<any>(null);
    const pdfRef = useRef<SubmitPdfHandle>(null);

    return (
        <main className="container mx-auto p-4 space-y-8 bg-white text-black">
            <h1 className="text-2xl font-bold text-center mb-8">
                PDF to Editable HTML Converter
            </h1>

            <div className="max-w-3xl mx-auto">
                <SubmitPdf
                    ref={pdfRef}
                    onContentChange={setContent}
                    className="mb-8"
                />
            </div>

            {content && (
                <div className="max-w-4xl mx-auto border rounded-lg shadow-sm">
                    <Editor content={content} className="min-h-[500px] p-6" />
                </div>
            )}
        </main>
    );
}
