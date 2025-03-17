"use client";

import { useEditor, EditorContent, JSONContent } from "@tiptap/react";
import { Node, mergeAttributes } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import Paragraph, { ParagraphOptions } from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import BulletList, { BulletListOptions } from "@tiptap/extension-bullet-list";
import OrderedList from "@tiptap/extension-ordered-list";
import ListItem, { ListItemOptions } from "@tiptap/extension-list-item";
import Heading, { HeadingOptions } from "@tiptap/extension-heading";
import CodeBlock, { CodeBlockOptions } from "@tiptap/extension-code-block";
import Image from "@tiptap/extension-image";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableCell from "@tiptap/extension-table-cell";
import TableHeader from "@tiptap/extension-table-header";
import Bold from "@tiptap/extension-bold";
import Italic from "@tiptap/extension-italic";
import Strike from "@tiptap/extension-strike";
import Underline from "@tiptap/extension-underline";
import TextStyle from "@tiptap/extension-text-style";
import Color from "@tiptap/extension-color";
import Highlight from "@tiptap/extension-highlight";
import Superscript from "@tiptap/extension-superscript";
import Blockquote from "@tiptap/extension-blockquote";
import katex from "katex";
import "katex/dist/katex.min.css";
import { useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import Link from "@tiptap/extension-link";

interface NodeAttributes {
    id: string | null;
}

interface HTMLElementWithNodeId extends HTMLElement {
    getAttribute(name: "data-node-id"): string | null;
}

interface HTMLElementWithFormula extends HTMLElement {
    getAttribute(name: "data-formula"): string;
}

interface MathAttributes {
    formula: string;
}

interface RenderHTMLProps {
    node?: {
        attrs: Record<string, any>;
    };
    HTMLAttributes: Record<string, any>;
}

// Define Math as a proper Node extension
const Math = Node.create({
    name: "math",
    group: "block",
    atom: true,

    addAttributes() {
        return {
            formula: {
                default: "",
                parseHTML: (element) => element.getAttribute("data-formula"),
                renderHTML: (attributes) => ({
                    "data-formula": attributes.formula,
                }),
            },
        };
    },

    parseHTML() {
        return [
            {
                tag: 'div[data-type="math"]',
            },
        ];
    },

    renderHTML({ node, HTMLAttributes }) {
        const formula = node.attrs.formula;
        const html = katex.renderToString(formula || "", {
            throwOnError: false,
            displayMode: true,
            output: "html",
            strict: false,
        });
        const container = document.createElement("div");
        container.innerHTML = html;
        return [
            "div",
            mergeAttributes(HTMLAttributes, {
                "data-type": "math",
                class: "math-block",
            }),
            container.firstChild,
        ];
    },
});

interface EditorProps {
    content: JSONContent;
    onChange?: (json: JSONContent) => void;
    className?: string;
}

const defaultContent: JSONContent = {
    type: "doc",
    content: [
        {
            type: "paragraph",
            content: [{ type: "text", text: "" }],
        },
    ],
};

function isValidContent(content: JSONContent): boolean {
    return (
        content &&
        typeof content === "object" &&
        content.type === "doc" &&
        Array.isArray(content.content)
    );
}

const hoverColor = "bg-blue-50";

const addNodeId = () => ({
    id: {
        default: null,
        parseHTML: (element: HTMLElementWithNodeId) =>
            element.getAttribute("data-node-id"),
        renderHTML: (attributes: NodeAttributes) => {
            const id = attributes.id || uuidv4();
            return {
                "data-node-id": id,
                "data-node-tooltip": `Node ID: ${id}`,
            };
        },
    },
});

export function Editor({ content, onChange, className }: EditorProps) {
    const editor = useEditor({
        extensions: [
            Document,
            Paragraph.configure({
                HTMLAttributes: {
                    class: `notion-block p-3 my-1 rounded-md hover:${hoverColor} transition-colors duration-100`,
                },
                addAttributes() {
                    return addNodeId();
                },
                renderHTML({ HTMLAttributes }: RenderHTMLProps) {
                    return ["p", mergeAttributes(HTMLAttributes)];
                },
            } as Partial<ParagraphOptions>),
            Text,
            Bold.configure({
                HTMLAttributes: {
                    class: "font-bold",
                },
            }),
            Italic.configure({
                HTMLAttributes: {
                    class: "italic",
                },
            }),
            Strike.configure({
                HTMLAttributes: {
                    class: "line-through",
                },
            }),
            Underline.configure({
                HTMLAttributes: {
                    class: "underline",
                },
            }),
            Superscript.configure({
                HTMLAttributes: {
                    class: "superscript",
                },
            }),
            Blockquote.configure({
                HTMLAttributes: {
                    class: "notion-blockquote pl-4 border-l-4 border-gray-300 my-2 py-1",
                },
            }),
            TextStyle,
            Color,
            Highlight.configure({
                multicolor: true,
            }),
            BulletList.configure({
                HTMLAttributes: {
                    class: `notion-list py-1 my-0.5 rounded-md hover:${hoverColor} transition-colors duration-100`,
                },
                addAttributes() {
                    return addNodeId();
                },
                renderHTML({ HTMLAttributes }: RenderHTMLProps) {
                    return ["ul", mergeAttributes(HTMLAttributes)];
                },
            } as Partial<BulletListOptions>),
            OrderedList.configure({
                HTMLAttributes: {
                    class: `notion-list py-1 my-0.5 rounded-md hover:${hoverColor} transition-colors duration-100`,
                },
            }),
            ListItem.configure({
                HTMLAttributes: {
                    class: `notion-list-item py-0.5 px-2 hover:${hoverColor} transition-colors duration-100`,
                },
                addAttributes() {
                    return addNodeId();
                },
                renderHTML({ HTMLAttributes }: RenderHTMLProps) {
                    return ["li", mergeAttributes(HTMLAttributes)];
                },
            } as Partial<ListItemOptions>),
            Heading.configure({
                levels: [1, 2],
                HTMLAttributes: {
                    class: `notion-heading py-2 my-1 rounded-md transition-colors duration-100`,
                },
                addAttributes() {
                    return {
                        ...addNodeId(),
                        level: {
                            default: 1,
                        },
                    };
                },
                renderHTML({ node, HTMLAttributes }: RenderHTMLProps) {
                    return [
                        `h${node!.attrs.level}`,
                        mergeAttributes(HTMLAttributes),
                    ];
                },
            } as Partial<HeadingOptions>),
            CodeBlock.configure({
                HTMLAttributes: {
                    class: "notion-code-block bg-gray-900 text-white font-mono p-4 rounded-lg my-2",
                },
                addAttributes() {
                    return {
                        ...addNodeId(),
                        language: {
                            default: null,
                        },
                    };
                },
                renderHTML({ HTMLAttributes }: RenderHTMLProps) {
                    return ["pre", mergeAttributes(HTMLAttributes)];
                },
            } as Partial<CodeBlockOptions>),
            Image.configure({
                HTMLAttributes: {
                    class: "notion-image max-w-full rounded-lg my-2",
                },
                allowBase64: true,
            }),
            Table.configure({
                HTMLAttributes: {
                    class: "notion-table min-w-full border-collapse my-4",
                },
            }),
            TableRow.configure({
                HTMLAttributes: {
                    class: "notion-table-row",
                },
            }),
            TableHeader.configure({
                HTMLAttributes: {
                    class: `notion-table-header ${hoverColor} font-semibold p-2 border border-gray-200`,
                },
            }),
            TableCell.configure({
                HTMLAttributes: {
                    class: "notion-table-cell p-2 border border-gray-200",
                },
            }),
            Math.configure({
                HTMLAttributes: {
                    class: "math-block",
                },
                addAttributes() {
                    return {
                        id: {
                            default: null,
                            parseHTML: (element: HTMLElementWithNodeId) =>
                                element.getAttribute("data-node-id"),
                            renderHTML: (attributes: NodeAttributes) => {
                                const id = attributes.id || uuidv4();
                                return {
                                    "data-node-id": id,
                                    "data-node-tooltip": `Node ID: ${id}`,
                                };
                            },
                        },
                        formula: {
                            default: "",
                        },
                    };
                },
            }),
            Link.configure({
                HTMLAttributes: {
                    class: "notion-link text-blue-600 hover:text-blue-800 hover:underline",
                    target: "_blank",
                    rel: "noopener noreferrer",
                },
                openOnClick: false,
                validate: (href) => /^https?:\/\//.test(href),
            }),
        ],
        content: isValidContent(content) ? content : defaultContent,
        editorProps: {
            attributes: {
                class: "notion-editor prose prose-sm sm:prose lg:prose-lg xl:prose-2xl mx-auto focus:outline-none bg-white text-black",
            },
        },
        onUpdate: ({ editor }) => {
            try {
                const jsonContent = editor.getJSON();
                if (isValidContent(jsonContent)) {
                    onChange?.(jsonContent);
                }
            } catch (error) {
                console.error("Failed to get editor content:", error);
            }
        },
    });

    // Update content when prop changes
    useEffect(() => {
        if (editor && content) {
            try {
                if (isValidContent(content)) {
                    const currentContent = editor.getJSON();
                    if (
                        JSON.stringify(content) !==
                        JSON.stringify(currentContent)
                    ) {
                        editor.commands.setContent(content, false);
                    }
                } else {
                    console.warn("Invalid content provided to Editor");
                    editor.commands.setContent(defaultContent, false);
                }
            } catch (error) {
                console.error("Failed to update editor content:", error);
                editor.commands.setContent(defaultContent, false);
            }
        }
    }, [content, editor]);

    return (
        <div className={`${className} notion-editor-wrapper max-w-4xl mx-auto`}>
            <style jsx global>{`
                .notion-editor-wrapper {
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                        Roboto, Oxygen, Ubuntu, Cantarell, "Open Sans",
                        "Helvetica Neue", sans-serif;
                    background-color: white;
                    color: black;
                }

                .notion-editor {
                    padding: 2rem 1rem;
                    background-color: white;
                    color: black;
                }

                .notion-block {
                    position: relative;
                    min-height: 1.5em;
                    margin-left: 0.1rem;
                    margin-right: 0.1rem;
                }

                p.notion-block {
                    padding: 0.75rem;
                    margin: 0.25rem;
                    border-radius: 0.375rem;
                    transition: background-color 100ms;
                }

                p.notion-block:hover {
                    background-color: rgb(239, 246, 255); /* blue-50 */
                }

                .notion-block:hover::before {
                    content: "";
                    position: absolute;
                    left: -1rem;
                    top: 50%;
                    transform: translateY(-50%);
                    width: 0.25rem;
                    height: 0.25rem;
                    border-radius: 50%;
                    background-color: #e5e7eb;
                }

                .notion-heading {
                    font-weight: 600;
                    padding: 0.5rem 0.75rem;
                    border-radius: 0.375rem;
                }

                .notion-heading:hover {
                    background-color: rgb(239, 246, 255); /* blue-50 */
                }

                h1.notion-heading {
                    font-size: 1.75rem;
                    line-height: 2rem;
                }

                h2.notion-heading {
                    font-size: 1.25rem;
                    line-height: 1.75rem;
                }

                .notion-list {
                    padding-left: 1.25rem;
                }

                .notion-list-item {
                    position: relative;
                    margin: 0; /* Reduced from 0.2rem */
                }

                .notion-list-item::before {
                    content: "";
                    position: absolute;
                    left: -1.25rem; /* Adjusted to match new padding */
                    top: 50%;
                    transform: translateY(-50%);
                }

                .notion-editor :focus {
                    outline: none;
                }

                .notion-editor p.is-empty::before {
                    content: "Type something...";
                    color: #9ca3af;
                    pointer-events: none;
                    float: left;
                    height: 0;
                }

                .notion-code-block {
                    font-family: "Fira Code", "Consolas", monospace;
                    line-height: 1.5;
                    tab-size: 2;
                    position: relative;
                }

                .notion-code-block::before {
                    content: attr(data-language);
                    position: absolute;
                    top: 0.5rem;
                    right: 1rem;
                    font-size: 0.75rem;
                    color: #9ca3af;
                }

                .notion-table {
                    border-radius: 0.5rem;
                    overflow: hidden;
                    width: 100%;
                }

                .notion-table-cell:first-child,
                .notion-table-header:first-child {
                    padding-left: 1rem;
                }

                .notion-table-cell:last-child,
                .notion-table-header:last-child {
                    padding-right: 1rem;
                }

                .notion-image {
                    display: block;
                    max-height: 20rem;
                    object-fit: contain;
                }

                .math-block {
                    padding: 1rem;
                    margin: 0.5rem 0;
                    background-color: white;
                    border-radius: 0.5rem;
                    overflow-x: auto;
                }

                .math-block:hover {
                    background-color: rgb(239, 246, 255); /* blue-50 */
                }

                .notion-table-row:nth-child(even) {
                    background-color: rgb(249, 250, 251); /* gray-50 */
                }

                /* Text formatting styles */
                .ProseMirror .text-highlight {
                    background-color: rgba(255, 255, 0, 0.3);
                    border-radius: 0.2em;
                    padding: 0.1em 0.2em;
                }

                .ProseMirror .text-highlight[style*="background-color"] {
                    background-color: var(--highlight-color);
                }

                .ProseMirror [style*="color"] {
                    border-radius: 0.2em;
                }

                .ProseMirror .underline {
                    text-decoration: underline;
                }

                .ProseMirror .line-through {
                    text-decoration: line-through;
                }

                .ProseMirror .font-bold {
                    font-weight: bold;
                }

                .ProseMirror .italic {
                    font-style: italic;
                }

                .ProseMirror .superscript {
                    vertical-align: super;
                    font-size: 0.75em;
                }

                .notion-blockquote {
                    background-color: rgb(249, 250, 251);
                    border-radius: 0.375rem;
                    margin: 0.5rem 0;
                    padding: 0.5rem 1rem;
                }

                .notion-blockquote:hover {
                    background-color: rgb(239, 246, 255);
                }

                /* Custom tooltip styles */
                [data-node-tooltip] {
                    position: relative !important;
                    cursor: pointer;
                }

                [data-node-tooltip]::after {
                    content: attr(data-node-tooltip);
                    visibility: hidden;
                    opacity: 0;
                    position: absolute;
                    top: 0;
                    right: 0;
                    background: #000;
                    color: white;
                    padding: 4px 8px;
                    border-radius: 4px;
                    font-size: 12px;
                    font-family: monospace;
                    white-space: nowrap;
                    z-index: 9999;
                    transform: translateY(-100%);
                    transition: opacity 0.2s ease-in-out;
                }

                [data-node-tooltip]:hover::after {
                    visibility: visible;
                    opacity: 1;
                }

                /* Add tooltip support to specific block types */
                .notion-block[data-node-tooltip],
                .notion-heading[data-node-tooltip],
                .notion-list-item[data-node-tooltip],
                .notion-code-block[data-node-tooltip],
                .math-block[data-node-tooltip] {
                    display: block;
                    min-height: 24px;
                }

                /* Ensure tooltips don't interfere with text selection */
                [data-node-tooltip]::after {
                    pointer-events: none;
                }

                /* Link styles */
                .notion-link {
                    color: rgb(37, 99, 235); /* blue-600 */
                    text-decoration: none;
                    transition: all 0.2s ease;
                }

                .notion-link:hover {
                    color: rgb(30, 64, 175); /* blue-800 */
                    text-decoration: underline;
                }

                /* Ensure links in tooltips are visible */
                [data-node-tooltip] a.notion-link::after {
                    color: white;
                }
            `}</style>
            <EditorContent editor={editor} />
        </div>
    );
}
