import { render, screen } from '@testing-library/react';
import { createMemoryRouter, Outlet, RouterProvider } from 'react-router';
import { expect, test } from 'vitest';
import '../i18n';
import { NotFoundPage, RouteError } from './NotFoundPage';

test('unknown child route shows a friendly page with a way home', () => {
  const router = createMemoryRouter(
    [{ path: '/', element: <Outlet />, children: [{ path: '*', element: <NotFoundPage /> }] }],
    { initialEntries: ['/nope/nothing'] },
  );
  render(<RouterProvider router={router} />);
  expect(screen.getByRole('link', { name: /dashboard/i })).toHaveAttribute('href', '/');
  expect(screen.queryByText(/developer/i)).toBeNull();
});

test('router errorElement hides the developer error screen', () => {
  const router = createMemoryRouter([{ path: '/', element: <div>home</div>, errorElement: <RouteError /> }], {
    initialEntries: ['/missing'],
  });
  render(<RouterProvider router={router} />);
  expect(screen.getByRole('alert')).toBeInTheDocument();
  expect(screen.queryByText(/hey developer/i)).toBeNull();
});
