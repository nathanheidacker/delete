'use client';

import { useCallback, useState, forwardRef, useImperativeHandle } from 'react';
import { useDropzone } from 'react-dropzone';

export interface SubmitPdfHandle {
    getHtml: () => string;
    clearHtml: () => void;
    isConverting: () => boolean;
    getError: () => string | null;
}

export interface SubmitPdfProps {
    onContentChange?: (html: string) => void;
    className?: string;
}

export const SubmitPdf = forwardRef<SubmitPdfHandle, SubmitPdfProps>(({ onContentChange, className = '' }, ref) => {
    const [data, setData] = useState<any>(null);
    const [error, setError] = useState<string>('');
    const [isLoading, setIsLoading] = useState(false);

    // Expose methods via ref
    useImperativeHandle(ref, () => ({
        getHtml: () => data,
        clearHtml: () => setData(null),
        isConverting: () => isLoading,
        getError: () => error || null
    }));

    const onDrop = useCallback(async (acceptedFiles: File[]) => {
        const file = acceptedFiles[0];
        
        // Reset states
        setError('');
        setData(null);
        setIsLoading(true);

        try {
            // Validate file type
            if (!file.type || file.type !== 'application/pdf') {
                throw new Error('Please upload a PDF file');
            }

            const formData = new FormData();
            formData.append('file', file);

            // Set a reasonable timeout
            const signal = AbortSignal.timeout(300000); // 5 minute timeout

            const response = await fetch('/api/py/convert', {
                method: 'POST',
                body: formData,
                signal,
                // Add headers to prevent timeouts
                headers: {
                    'Connection': 'keep-alive',
                    'Keep-Alive': 'timeout=300' // 5 minutes in seconds
                }
            });

            const result = await response.json();
            
            if (!response.ok) {
                throw new Error(result.error || 'Failed to convert PDF');
            }

            setData(result);
            console.log(result)
            onContentChange?.(result);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'An error occurred');
        } finally {
            setIsLoading(false);
        }
    }, [onContentChange]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: {
            'application/pdf': ['.pdf']
        },
        multiple: false
    });

    return (
        <div className={`w-full ${className}`}>
            <div
                {...getRootProps()}
                className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
                    ${isDragActive 
                        ? 'border-blue-500 bg-blue-50' 
                        : 'border-gray-300 hover:border-gray-400'
                    }
                    ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}
                `}
            >
                <input {...getInputProps()} />
                {isLoading ? (
                    <p className="text-gray-600">Converting PDF...</p>
                ) : isDragActive ? (
                    <p className="text-blue-500">Drop the PDF file here</p>
                ) : (
                    <p className="text-gray-600">
                        Drag and drop a PDF file here, or click to select
                    </p>
                )}
            </div>

            {error && (
                <div className="mt-4 p-4 bg-red-50 text-red-600 rounded-lg">
                    {error}
                </div>
            )}
        </div>
    );
});

SubmitPdf.displayName = 'SubmitPdf';
