"""
This module documents the interface to the OpenID server library.  The
only part of the library which has to be used and isn't documented
here is the store for associations.  See the C{L{openid.store}}
package for more information on stores.


OVERVIEW
========

    There are two different classes of requests that identity servers
    need to be able to handle.  First are the requests made directly
    by identity consumers.  Second are the requests made indirectly,
    via redirects sent to the user's web browser.

    The first class are the requests made to it directly by identity
    consumers.  These are HTTP POST requests made to the published
    OpenID server URL.  There are two types of these requests, requests
    to create an association, and requests to verify identity requests
    signed with a secret that is entirely private to the server.

    The second class are the requests made through redirects.  These
    are HTTP GET requests coming from the user's web browser.  For
    these requests, the identity server must perform several steps.
    It has to determine the identity of the user making the request,
    determine if they are allowed to use the identity requested, and
    then take the correct action depending on the exact form of the
    request and the answers to those questions.


LIBRARY DESIGN
==============

    This server library is designed to make dealing with both classes
    of requests as straightforward as possible.

    At a high level, there are two parts of the library which are
    important.  First, there is the C{L{OpenIDServer}} class in this
    module.  Second, there is the C{L{openid.store}} package, which
    contains information on the necessary persistent state mechanisms,
    and several implementations.

    There is also a C{L{LowLevelServer}} class available if you need
    special handling that isn't available through the
    C{L{OpenIDServer}} class.


STORES
======

    The OpenID server needs to maintain state between requests in
    order to function.  Its mechanism for doing this is called a
    store.  The store interface is defined in
    C{L{openid.store.interface.OpenIDStore}}.  Additionally, several
    concrete store implementations are provided, so that most sites
    won't need to implement a custom store.  For a store backed by
    flat files on disk, see
    C{L{openid.store.filestore.FileOpenIDStore}}.  For stores based
    on MySQL or SQLite, see the C{L{openid.store.sqlstore}} module.


USING THIS LIBRARY
==================

    This library is designed to be easy to use for handling OpenID
    requests.  There is, however, additional work a site has to do as
    an OpenID server which is beyond the scope of this library.  That
    work consists primarily of creating a couple additional pages for
    handling verifying that the user wants to confirm their identity
    to the consumer site.  Implementing an OpenID server using this
    library should follow this basic plan:

    First, you need to choose a URL to be your OpenID server URL.
    This URL needs to be able to handle both GET and POST requests,
    and distinguish between them.

    Next, you need to have some system for mapping identity URLs to
    users of your system.  The easiest method to do this is to insert
    an appropriate <link> tag into your users' public pages.  See the
    U{OpenID spec<http://openid.net/specs.bml#linkrel>} for the
    precise format the <link> tag needs to follow.  Then, each user's
    public page URL is that user's identity URL.  There are many
    alternative approaches, most of which should be fairly obvious.

    The next step is to write the code to handle requests to the
    server URL.  When a request comes in, several steps need to take
    place:

        1. Get an C{L{OpenIDServer}} instance with an appropriate
           store.  This may be a previously created instance, or a new
           one, whichever is convenient for your application.

        2. Call the C{L{OpenIDServer}} instance's
           C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}}
           method.  The first argument is a string indicating the HTTP
           method used to make the request.  This should be either
           C{'GET'} or C{'POST'}, the two HTTP methods that OpenID
           uses.  The second argument is the GET or POST (as
           appropriate) arguments provided for this request, parsed
           into a C{dict}-like structure.  The third argument is a
           callback function for determining if authentication
           requests can proceed.  For more details on the callback
           function, see the the documentation for
           C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}}.

        3. The return value from that call is a pair, (status, info).
           Depending on the status value returned, there are several
           different actions you might take.  See the documentation
           for the C{L{getOpenIDResponse
           <OpenIDServer.getOpenIDResponse>}} method for a full list
           of possible results, what they mean, and what the
           appropriate action for each is.

    Processing all the results from that last step is fairly simple,
    but it involves adding a few additional pages to your site.  There
    needs to be a page about OpenID that users who visit the server
    URL directly can be shown, so they have some idea what the URL is
    for.  It doesn't need to be a fancy page, but there should be one.

    Usually the C{L{DO_AUTH}} case will also require at least one
    page, and perhaps more.  These pages could be arranged many
    different ways, depending on your site's policies on interacting
    with its users.

    Overall, implementing an OpenID server is a fairly straightforward
    process, but it requires significant application-specific work
    above what this library provides.


@var REDIRECT: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when the
    user should be sent a redirect.


@var DO_AUTH: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when the
    library has determined that it's up to the application and user to
    fix the reason the library isn't authorized to return a successful
    authentication response.


@var DO_ABOUT: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when there
    were no OpenID arguments provided at all.  This is typically the
    case when somebody notices the <link> tag in a web page, wonders
    what it's there for, and decides to type it in.  The standard
    behavior in this case is to show a page with a small explanation
    of OpenID.


@var REMOTE_OK: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when the
    server should send a 200 response code and an exact message body.
    This is for informing a remote site everything worked correctly.


@var REMOTE_ERROR: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when the
    server should send a 400 response code and an exact message body.
    This is for informing a remote site that an error occured while
    processing the request.


@var LOCAL_ERROR: This status code is returned by
    C{L{getOpenIDResponse<OpenIDServer.getOpenIDResponse>}} when
    something went wrong, and the library isn't able to find an
    appropriate in-protocol response.  When this happens, a short
    plaintext description of the error will be provided.  The server
    will probably want to return some sort of error page here, but its
    contents are not strictly prescribed, like those of the
    C{L{REMOTE_ERROR}} case.


@sort: REDIRECT, DO_AUTH, DO_ABOUT, REMOTE_OK, REMOTE_ERROR,
    LOCAL_ERROR, OpenIDServer
"""

import time
import urllib
import cgi

from openid import cryptutil
from openid import kvform
from openid import oidutil
from openid.dh import DiffieHellman
from openid.server.trustroot import TrustRoot
from openid.association import Association

_signed_fields = ['mode', 'identity', 'return_to']

REDIRECT     = 'redirect'
DO_AUTH      = 'do_auth'
DO_ABOUT     = 'do_about'

REMOTE_OK    = 'exact_ok'
REMOTE_ERROR = 'exact_error'

LOCAL_ERROR  = 'local_error'

class OpenIDServer(object):
    """
    This class is the interface to the OpenID server logic.  Instances
    contain no per-request state, so a single instance can be reused
    (or even used concurrently by multiple threads) as needed.

    This class presents an extremely high-level interface to the
    OpenID server library via the C{L{getOpenIDResponse}} method.
    Server implementations that wish to handle dispatching themselves
    can use the interface provided by the C{L{LowLevelServer}} class.


    @sort: __init__, getOpenIDResponse
    """

    def __init__(self, server_url, store):
        """
        This method initializes a new C{L{OpenIDServer}} instance.
        C{L{OpenIDServer}} instance contain no per-request internal
        state, so they can be reused or used concurrently by multiple
        threads, if desired.


        @param server_url: This is the server's OpenID URL.  It is
            used whenever the server needs to generate a URL that will
            cause another OpenID request to be made, which can happen
            in authentication requests.  It's also used as part of the
            key for looking up and storing the server's secrets.

        @type server_url: C{str}


        @param store: This in an object implementing the
            C{L{openid.store.interface.OpenIDStore}} interface which
            the library will use for persistent storage.  See the
            C{L{OpenIDStore<openid.store.interface.OpenIDStore>}}
            documentation for more information on stores and various
            implementations.  Note that the store used for the server
            must not be a dumb-style store.  It's not possible to be a
            functional OpenID server without persistent storage.

        @type store: An object implementing the
            C{L{openid.store.interface.OpenIDStore}} interface
        """
        self.low_level = LowLevelServer(server_url, store)

    def getOpenIDResponse(self, http_method, args, is_authorized):
        """
        This method processes an OpenID request, and determines the
        proper response to it.  It then communicates what that
        response should be back to its caller via return codes.

        The return value of this method is a pair, C{(status, info)}.
        The first value is the status code describing what action
        should be taken.  The second value is additional information
        for taking that action.

        The following return codes are possible:

            1.  C{L{REDIRECT}} - This code indicates that the server
                should respond with an HTTP redirect.  In this case,
                C{info} is the URL to redirect the client to.

            2.  C{L{DO_AUTH}} - This code indicates that the server
                should take whatever actions are necessary to allow
                this authentication to succeed or be cancelled, then
                try again.  In this case C{info} is a
                C{AuthorizationInfo} object, which contains additional
                useful information.

            3.  C{L{DO_ABOUT}} - This code indicates that the server
                should display a page containing information about
                OpenID.  This is returned when it appears that a user
                entered an OpenID server URL directly in their
                browser, and the request wasn't an OpenID request at
                all.  In this case C{info} is C{None}.

            4.  C{L{REMOTE_OK}} - This code indicates that the server
                should return content verbatim in response to this
                request, with an HTTP status code of 200.  In this
                case, C{info} is a C{str} containing the content to
                return.

            5.  C{L{REMOTE_ERROR}} - This code indicates that the
                server should return content verbatim in response to
                this request, with an HTTP status code of 400.  In
                this case, C{info} is a C{str} containing the content
                to return.

            6.  C{L{LOCAL_ERROR}} - This code indicates an error that
                can't be handled within the protocol.  When this
                happens, the server may inform the user that an error
                has occured as it sees fit.  In this case, C{info} is
                a short description of the error.


        @param http_method: This is a string describing the HTTP
            method used to make the current request.  The only
            expected values are C{'GET'} and C{'POST'}, though
            capitalization will be ignored.  Any value other than one
            of the expected ones will result in a LOCAL_ERROR return
            code.

        @type http_method: C{str}


        @param args: This should be a C{dict}-like object that
            contains the parsed, unescaped arguments that were sent
            with the OpenID request being handled.  The keys and
            values in the dictionary should both be either C{str} or
            C{unicode} objects.

        @type args: a C{dict}-like object


        @param is_authorized: This is a callback function which this
            C{L{OpenIDServer}} instance will use to determine the
            result of an authentication request.  The function will be
            called with two C{str} arguments, C{identity_url} and
            C{trust_root}.  It should return a C{bool} value
            indicating whether this identity request is authorized to
            succeed.

            The function needs to perform two seperate tasks, and
            return C{True} only if it gets a positive result from
            each.

            The first task is to determine the user making this
            request, and if they are authorized to claim the identity
            URL passed to the function.  If the user making this
            request isn't authorized to claim the identity URL, the
            callback should return C{False}.

            The second task is to determine if the user will allow the
            trust root in question to determine his or her identity.
            If they have not previously authorized the trust root to
            know they're identity the callback should return C{False}.

            If neither of those returned C{False}, the callback should
            return C{True}.  An example callback might look like this::

                def is_authorized(identity_url, trust_root):
                    user = getUserName()
                    if user is None:
                        return False

                    if identity_url != getIdentityUrl(user):
                        return False

                    if trust_root not in getTrustRoots(user):
                        return False

                    return True

            That's obviously a pseudocode-ish example, but it conveys
            the important steps.  This callback should work only with
            information already submitted, ie. the user already logged
            in and the trust roots they've already approved.  It is
            important that this callback does not attempt to interact
            with the user.  Doing so would lead to violating the
            OpenID specification when the server is handling
            checkid_immediate requests.

        @type is_authorized: A function, taking two C{str} objects and
            returning a C{bool}.


        @return: A pair, C{(status, value)} which describes the
            appropriate response to an OpenID request, as above.  The
            first value will always be one of the constants defined in
            this package.

        @rtype: (C{str}, depends on the first)
        """
        if http_method.upper() == 'GET':
            trust_root = args.get('openid.trust_root')
            if not trust_root:
                trust_root = args.get('openid.return_to')

            identity_url = args.get('openid.identity')
            if identity_url is None or trust_root is None:
                authorized = 0 # not False for 2.2 compatibility
            else:
                authorized = is_authorized(identity_url, trust_root)

            return self.low_level.getAuthResponse(authorized, args)

        elif http_method.upper() == 'POST':
            mode = args.get('openid.mode')
            if mode == 'associate':
                return self.low_level.associate(args)

            elif mode == 'check_authentication':
                return self.low_level.checkAuthentication(args)

            else:
                err = 'Invalid openid.mode (%r) for POST requests' % mode
                return self.low_level.postError(err)

        else:
            err = 'HTTP method %r is not valid with OpenID' % (http_method,)
            return LOCAL_ERROR, err


class AuthorizationInfo(object):
    """
    This is a class to encapsulate information that is useful when
    interacting with a user to determine if an authentication request
    can be authorized to succeed.  This class provides methods to get
    the identity URL and trust root from the request that failed.
    Given those, the server can determine what needs to happen in
    order to allow the request to proceed, and can ask the user to
    perform the necessary actions.

    The user may choose to either perform the actions or not.  If they
    do, the server should try to perform the request OpenID request
    again.  If they choose not to, and inform the server by hitting
    some form of cancel button, the server should redirect them back
    to the consumer with a notification of that for the consumer.

    This class provides two approaches for each of those actions.  The
    server can either send the user redirects which will cause the
    user to retry the OpenID request, or it can help perform those
    actions without involving an extra redirect, producing output that
    works like that of C{L{OpenIDServer.getOpenIDResponse}}.

    Both approaches work equally well, and you should choose the one
    that fits into your framework better.

    The C{L{retry}} and C{L{cancel}} methods produce C{(status,
    info)} pairs that should be handled exactly like the responses
    from C{L{OpenIDServer.getOpenIDResponse}}.

    The C{L{getRetryURL}} and C{L{getCancelURL}} methods return URLs
    to which the user can be redirected to automatically retry or
    cancel this OpenID request.
    """

    def __init__(self, server_url, args):
        """
        This creates a new C{L{AuthorizationInfo}} object for the
        given values.

        This constructor is intended primarily for use by the library.


        @param server_url: This is the OpenID server's url.  It's used
            to calculate the retry URL, if requested.

        @type server_url: C{str}


        @param args: The query arguments for this request.  This class
            strips out all non-OpenID arguments.

        @type args: a C{dict}-like object
        """
        self.server_url = server_url

        return_to = args.get('openid.return_to')

        self.identity_url = args.get('openid.identity')
        self.trust_root = args.get('openid.trust_root') or return_to

        cancel_args = {'openid.mode': 'cancel'}
        self.cancel_url = oidutil.appendArgs(return_to, cancel_args)

        self.args = dict(args.iteritems())

    def retry(self, openid_server, is_authorized):
        """
        This method retries an OpenID authentication request.


        @param openid_server: This is an instance of
            C{L{OpenIDServer}} that will perform the retry.

        @type openid_server: C{L{OpenIDServer}}


        @param is_authorized: This is a callback to determine if the
            request is authorized, as documented in
            C{L{OpenIDServer.getOpenIDResponse}}.

        @type is_authorized: A function, taking two C{str} objects and
            returning a C{bool}.


        @return: A C{(status, info)} pair, to be handled like the
            return value from C{L{OpenIDServer.getOpenIDResponse}}.

        @rtype: (C{str}, depends on the first)
        """
        return openid_server.getOpenIDResponse('GET', self.args, is_authorized)

    def cancel(self):
        """
        This method cancels an OpenID authentication request.


        @return: A C{(status, info)} pair, to be handled like the
            return value from C{L{OpenIDServer.getOpenIDResponse}}.

        @rtype: (C{str}, depends on the first)
        """
        return REDIRECT, self.cancel_url

    def getRetryURL(self):
        """
        This method returns a URL for retrying the OpenID request that
        generated this C{L{AuthorizationInfo}} object.  If the user's
        web browser is redirected to this URL, the request will be
        retried automatically.


        @return: A URL which will cause an OpenID request on this
            server.

        @rtype: C{str}
        """
        return oidutil.appendArgs(self.server_url, self.args)

    def getCancelURL(self):
        """
        This method returns a URL which cancels the OpenID request
        that generated this C{L{AuthorizationInfo}} object.  If the
        user's web browser is redirected to this URL, the request will
        be canceled.


        @return: A URL which is a response cancelling this OpenID
            request.

        @rtype: C{str}
        """
        return self.cancel_url

    def getIdentityURL(self):
        """
        This method returns the identity URL in the request that
        generated this C{L{AuthorizationInfo}} object.


        @return: The identity URL this request is asking about.

        @rtype: C{str}
        """
        return self.identity_url

    def getTrustRoot(self):
        """
        This method returns the trust root in the request that
        generated this C{L{AuthorizationInfo}} object.


        @return: The trust root this request is on behalf of.

        @rtype: C{str}
        """
        return self.trust_root

    def serialize(self):
        """
        This method generates a string representing this
        C{L{AuthorizationInfo}} object.  The result string can be used
        with the C{L{deserialize}} method to create a new
        C{L{AuthorizationInfo}} object with the same functionality as
        this one.


        @return: A serialized form of this object.

        @rtype: C{str}
        """
        return self.server_url + '|' + urllib.urlencode(self.args)

    def deserialize(cls, string_form):
        """
        This method create a C{L{AuthorizationInfo}} object from a
        string created by the C{L{serialize}} method of the class.


        @param string_form: This is a string that came from a
            C{L{serialize}} call on a C{L{AuthorizationInfo}}
            instance.

        @type string_form: C{str}


        @return: A new C{L{AuthorizationInfo}} object

        @rtype: C{L{AuthorizationInfo}}
        """
        server_url, args = string_form.split('|', 1)
        return cls(server_url, dict(cgi.parse_qsl(args)))

    deserialize = classmethod(deserialize)


class LowLevelServer(object):
    """
    This class provides direct access to most of the low-level
    functionality of the OpenID server.

    It is not recommended that you use this class directly if you can
    avoid it.  Using it requires manually handling dispatching among
    the methods, which is done automatically in the C{L{OpenIDServer}}
    class.


    @cvar SECRET_LIFETIME: This is the lifetime that secrets generated
        by this library are valid for, in seconds.

    @type SECRET_LIFETIME: C{int}
    """
    
    SECRET_LIFETIME = 14 * 24 * 60 * 60 # 14 days, in seconds

    def __init__(self, server_url, store):
        """
        This initializes a new C{L{LowLevelServer}} instance.


        @param server_url: This is the server's OpenID URL.  It is
            used whenever the server needs to generate a URL that will
            cause another OpenID request to be made, which can happen
            in authentication requests.  It's also used as part of the
            key for looking up and storing the server's secrets.

        @type server_url: C{str}


        @param store: This in an object implementing the
            C{L{openid.store.interface.OpenIDStore}} interface which
            the library will use for persistent storage.  See the
            C{L{OpenIDStore<openid.store.interface.OpenIDStore>}}
            documentation for more information on stores and various
            implementations.  Note that the store used for the server
            must not be a dumb-style store.  It's not possible to be a
            functional OpenID server without persistent storage.

        @type store: An object implementing the
            C{L{openid.store.interface.OpenIDStore}} interface
        """
        self.url = server_url
        self.normal_key = server_url + '|normal'
        self.dumb_key = server_url + '|dumb'

        if store.isDumb():
            raise ValueError, 'OpenID servers cannot use a dumb store.'

        self.store = store


    def getAuthResponse(self, authorized, args):
        """
        This method determines the correct response to make to an
        authentication request.

        This method always returns a pair.  The first value of the
        pair indicates what action the server should take to respond
        to this request.  The second value is additional information
        to use when taking that action.


        @param authorized: This is a value which indicates whether the
            server is authorized to tell the consumer that the user
            owns the identity URL in question.  For this to be true,
            the server must check that the user making this request is
            the owner of the identity URL in question, and that the
            user has given the consumer permission to learn his or her
            identity.  The server must determine this value based on
            information it already has, without interacting with the
            user.  If it has insufficient information to produce a
            definite C{True}, it must pass in C{False}.

        @type authorized: C{bool}


        @param args: This should be a C{dict}-like object that
            contains the parsed, unescaped query arguments that were
            sent with the OpenID request being handled.  The keys and
            values in the dictionary should both be either C{str} or
            C{unicode} objects.

        @type args: a C{dict}-like object


        @return: Returns a pair, C{(status, info)}.  See
            C{L{OpenIDServer.getOpenIDResponse}} for a description of
            what return status values mean.  This method can return
            all of the status values except C{L{REMOTE_OK}} and
            C{L{REMOTE_ERROR}}.

        @rtype: (C{str}, depends on the first)
        """
        mode = args.get('openid.mode')

        if mode not in ['checkid_immediate', 'checkid_setup']:
            err = 'invalid openid.mode (%r) for GET requests' % mode
            return self.getError(args, err)

        identity = args.get('openid.identity')
        if identity is None:
            return self.getError(args, 'No identity specified')

        trust_root = args.get('openid.trust_root')
        if trust_root is None:
            trust_root = args.get('openid.return_to')

        tr = TrustRoot.parse(trust_root)
        if tr is None:
            err = 'Malformed trust_root: %r' % (trust_root,)
            return self.getError(args, err)

        return_to = args.get('openid.return_to')
        if return_to is None:
            return self.getError(args, 'No return_to URL specified')

        if not tr.validateURL(return_to):
            err = 'return_to(%s) not valid against trust_root(%s)' % \
                  (return_to, trust_root)
            return self.getError(args, err)

        if not authorized:
            if mode == 'checkid_immediate':
                nargs = dict(args)
                nargs['openid.mode'] = 'checkid_setup'
                setup_url = oidutil.appendArgs(self.url, nargs)
                rargs = {
                    'openid.mode': 'id_res',
                    'openid.user_setup_url': setup_url
                    }
                return REDIRECT, oidutil.appendArgs(return_to, rargs)

            elif mode == 'checkid_setup':
                return DO_AUTH, AuthorizationInfo(self.url, args)

            else:
                raise AssertionError, 'unreachable'

        reply = {
            'openid.mode': 'id_res',
            'openid.return_to': return_to,
            'openid.identity': identity,
            }

        store = self.store
        assoc_handle = args.get('openid.assoc_handle')
        if assoc_handle:
            assoc = store.getAssociation(self.normal_key, assoc_handle)

            # fall back to dumb mode if assoc_handle not found,
            # and send the consumer an invalidate_handle message
            if assoc is None or assoc.expiresIn <= 0:
                if assoc is not None and assoc.expiresIn <= 0:
                    store.removeAssociation(self.normal_key, assoc.handle)

                assoc = self.createAssociation('HMAC-SHA1')
                store.storeAssociation(self.dumb_key, assoc)
                reply['openid.invalidate_handle'] = assoc_handle
        else:
            assoc = self.createAssociation('HMAC-SHA1')
            store.storeAssociation(self.dumb_key, assoc)

        reply['openid.assoc_handle'] = assoc.handle

        assoc.addSignature(_signed_fields, reply)

        return REDIRECT, oidutil.appendArgs(return_to, reply)

    def associate(self, args):
        """
        This method performs the C{openid.mode=associate} action.


        @param args: This should be a C{dict}-like object that
            contains the parsed, unescaped query arguments that were
            sent with the OpenID request being handled.  The keys and
            values in the dictionary should both be either C{str} or
            C{unicode} objects.

        @type args: a C{dict}-like object


        @return: Returns a pair, C{(status, info)}.  See
            C{L{OpenIDServer.getOpenIDResponse}} for a description of
            what return status values mean.  This method will return
            only the C{L{REMOTE_OK}} and C{L{REMOTE_ERROR}} status
            codes.

        @rtype: C{(str, str)}
        """
        reply = {}
        assoc_type = args.get('openid.assoc_type', 'HMAC-SHA1')
        assoc = self.createAssociation(assoc_type)

        if assoc is None:
            err = 'unable to create an association for type %r' % assoc_type
            return self.postError(err)
        else:
            self.store.storeAssociation(self.normal_key, assoc)

        reply.update({
            'assoc_type': 'HMAC-SHA1',
            'assoc_handle': assoc.handle,
            'expires_in': str(assoc.expiresIn),
            })

        session_type = args.get('openid.session_type')
        if session_type:
            if session_type == 'DH-SHA1':
                modulus = args.get('openid.dh_modulus')
                generator = args.get('openid.dh_gen')

                try:
                    dh = DiffieHellman.fromBase64(modulus, generator)
                except ValueError:
                    err = "Please convert to two's complement correctly"
                    return self.postError(err)

                consumer_public = args.get('openid.dh_consumer_public')
                if consumer_public is None:
                    err = 'Missing openid.dh_consumer_public'
                    return self.postError(err)

                cpub = cryptutil.base64ToLong(consumer_public)
                if cpub < 0:
                    err = "Please convert to two's complement correctly"
                    return self.postError(err)

                mac_key = dh.xorSecret(cpub, assoc.secret)

                reply.update({
                    'session_type': session_type,
                    'dh_server_public': cryptutil.longToBase64(dh.public),
                    'enc_mac_key': oidutil.toBase64(mac_key),
                    })
            else:
                return self.postError('session_type must be DH-SHA1')
        else:
            reply['mac_key'] = oidutil.toBase64(assoc.secret)

        return REMOTE_OK, kvform.dictToKV(reply)

    def checkAuthentication(self, args):
        """
        This method performs the C{openid.mode=check_authentication}
        action.


        @param args: This should be a C{dict}-like object that
            contains the parsed, unescaped query arguments that were
            sent with the OpenID request being handled.  The keys and
            values in the dictionary should both be either C{str} or
            C{unicode} objects.

        @type args: a C{dict}-like object


        @return: Returns a pair, C{(status, info)}.  See
            C{L{OpenIDServer.getOpenIDResponse}} for a description of
            what return status values mean.  This method will return
            only the C{L{REMOTE_OK}} and C{L{REMOTE_ERROR}} status
            codes.

        @rtype: C{(str, str)}
        """
        assoc_handle = args.get('openid.assoc_handle')

        if assoc_handle is None:
            return self.postError('Missing openid.assoc_handle')

        assoc = self.store.getAssociation(self.dumb_key, assoc_handle)

        reply = {}
        if assoc and assoc.expiresIn > 0:
            signed = args.get('openid.signed')
            if signed is None:
                return self.postError('Missing openid.signed')

            sig = args.get('openid.sig')
            if sig is None:
                return self.postError('Missing openid.sig')

            to_verify = dict(args)
            to_verify['openid.mode'] = 'id_res'

            signed_fields = signed.strip().split(',')
            tv_sig = assoc.signDict(signed_fields, to_verify)

            if tv_sig == sig:
                self.store.removeAssociation(self.normal_key, assoc_handle)
                is_valid = 'true'

                invalidate_handle = args.get('openid.invalidate_handle')
                if invalidate_handle:
                    if not self.store.getAssociation(self.normal_key,
                                                     invalidate_handle):
                        reply['invalidate_handle'] = invalidate_handle
            else:
                is_valid = 'false'

        else:
            if assoc:
                self.store.removeAssociation(self.dumb_key, assoc_handle)

            is_valid = 'false'

        reply['is_valid'] = is_valid
        return REMOTE_OK, kvform.dictToKV(reply)

    def createAssociation(self, assoc_type):
        """
        This method is used internally by the OpenID library to create
        new associations to send to consumers.


        @param assoc_type: The type of association to request.  Only
            C{'HMAC-SHA1'} is currently supported.

        @type assoc_type: C{str}


        @return: A new association of the requested type, or C{None}
            if the requested type isn't recognized.

        @rtype: C{L{openid.association.Association}} or C{NoneType}
        """
        if assoc_type == 'HMAC-SHA1':
            secret = cryptutil.getBytes(20)
        else:
            return None

        uniq = oidutil.toBase64(cryptutil.getBytes(4))
        handle = '{%s}{%x}{%s}' % (assoc_type, int(time.time()), uniq)

        assoc = Association.fromExpiresIn(
            self.SECRET_LIFETIME, handle, secret, assoc_type)

        return assoc

    def getError(self, args, msg):
        """
        This method is used to generate the correct error response if
        an error occurs during a GET request.


        @param args: This should be a C{dict}-like object that
            contains the parsed, unescaped query arguments that were
            sent with the OpenID request being handled.  The keys and
            values in the dictionary should both be either C{str} or
            C{unicode} objects.

        @type args: a C{dict}-like object


        @param msg: The error message to send.

        @type msg: C{str}


        @return: Returns a pair, C{(status, info)}.  See
            C{L{OpenIDServer.getOpenIDResponse}} for a description of
            what return status values mean.  This method can return
            all of the status values except C{L{REMOTE_OK}} and
            C{L{REMOTE_ERROR}}.

        @rtype: (C{str}, depends on the first)
        """
        return_to = args.get('openid.return_to')
        if return_to:
            err = {
                'openid.mode': 'error',
                'openid.error': msg
                }
            return REDIRECT, oidutil.appendArgs(return_to, err)
        else:
            for k, _ in args.iteritems():
                if k.startswith('openid.'):
                    return LOCAL_ERROR, msg

            return DO_ABOUT, None

    def postError(self, msg):
        """
        This method is used to generate the correct error response if
        an error occurs during a POST request.


        @param msg: The error message to send.

        @type msg: C{str}


        @return: Returns a pair, C{(status, info)}.  See
            C{L{OpenIDServer.getOpenIDResponse}} for a description of
            what return status values mean.  This method will return
            only the C{L{REMOTE_OK}} and C{L{REMOTE_ERROR}} status
            codes.

        @rtype: C{(str, str)}
        """
        return REMOTE_ERROR, kvform.dictToKV({'error': msg})