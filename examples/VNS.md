---
up:
  - "[[Vanity Name Servers]]"
tags:
  - "#project/work/dnsimple/video/vns"
---


> [!QUOTE] Original Capture
> [What Are Vanity Name Servers? - DNSimple Help](https://support.dnsimple.com/articles/what-are-vanity-name-servers/)

# Intro

When you want to visit a website, your computer needs to know where to get the content to display. The first stop is a domain name’s name servers. These name servers contain the DNS records that point to the IP address(es) of the server that serves the website’s content.

# What are Vanity Name Servers?

Typically, a name server uses the name of a DNS service (such as ns1.dnsimple.com), but sometimes you might want to have your domain name on those name servers. However, owning, managing, and upkeep on a server can be quite the hassle. That’s where a feature called Vanity Name Servers comes into play.

Vanity name servers provide a name server endpoint at a domain that you own without the need to host your own name server. The resolution of records and hosting of DNS is still handled by the provider, but you get the outward appearance of your domain name when using name servers.

# How do they work?

Instead of using a generic name server, your domain is delegated to its own subdomain. This does present a problem, however. In order to resolve the subdomain, the resolver has to query its own name server, which creates a cyclical dependency.

To get around this, something called a glue record is used, which allows the TLD to provide the IP addresses of your vanity name server host names directly. Essentially, the resolver receives the generic name server’s IP when querying the custom name servers despite them being a subdomain of your name. This is why they are called vanity name servers: they allow a custom name for the resolving name servers without actually hosting a separate name server.

# Why use them?

Why might one want to use Vanity Name Servers? The value for a large organization with many domains is clear: having your DNS resolution be branded to your name makes you look like you own the whole vertical of your networking, making your infrastructure appear more professional. This is why vanity name servers are sometimes referred to as branded or white-labeled DNS, and are helpful for any organization with a large user base or any company that wants a professional look for their internet infrastructure.

Other than branding, why else might you want to use vanity name servers? When you give it a bit of thought, a quite obvious reason is security. Using vanity name servers means that you don’t need to manage security of your own name server, nor the maintenance of it. As a result of using a provider in this manner, you don’t need to worry about downtime for those tasks, and if you do have a problem it’s quite easy to swap out your underlying provider quickly.

Some TLDs, such as .bank or .insurance require in-zone name servers (these are name servers that contain .bank/.insurance). By using vanity name servers, you can easily meet this requirement – and appear cutting-edge while using your own domain name!

# Conclusion

Using all of the power of a DNS provider such as DNSimple while making it appear that your names are delegated to your own name servers provides a level of vertical control hard to match without managing separate DNS instances yourself. Vanity name servers provide a secure way to back the resolving zones that your domains’ delegated name server return, while keeping all benefits of hosting your DNS with a provider.

Like having your brand’s identity on your office door, using vanity name servers can bring a professional look to your internet infrastructure. This helps keep your domains looking professional while keeping all of the power of an external DNS provider.

Vanity name servers offer significant advantages when you manage a large number of domains. That's why DNSimple offers vanity name servers on our Enterprise plan. If you would like to use vanity name servers contact our team for more information.

# CTA

Wondering if vanity name servers are a good choice for your domains? We've got answers! Contact our team at:
https://dnsimple.com/sales

Want to give DNSimple a try risk free? Visit:
dnsimple.com/signup

Not using DNSimple yet? Give us a try free for 30 days, and see how simple and secure domain management can be.



Need more information about how DNS works with DNSimple?
Check out other videos on our channel, and read our comic linked in the description.

If you want more information about SSL SAN Certificates, watch this video next.
(link video of How DNS Works: SSL SAN Certificates with DNSimple)
