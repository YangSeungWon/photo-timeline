import type { Metadata } from 'next'

export const metadata: Metadata = {
    title: 'Photo Timeline',
    description: 'Photo sharing and timeline visualization',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body>{children}</body>
        </html>
    )
} 